/* Durable single semantic command; exact viewport retries cannot re-scroll. */
(() => {
  async function run(tabId,command) {
    const path=`/api/bridge/discovery/${command.id}`;
    const state=()=>request(`${path}/control?extension_id=${encodeURIComponent(chrome.runtime.id)}`);
    const finish=stop_reason=>request(path+'/finish',{extension_id:chrome.runtime.id,stop_reason});
    let current=await state();
    if(current.terminal){await chrome.storage.local.remove('activeDiscovery');await chrome.storage.local.remove('pendingDiscoveryStep');return;}
    const tab=await chrome.tabs.get(tabId);
    if(!ProductHunterDiscovery.searchPage(tab.url,command.query)){await finish('error');await chrome.storage.local.remove('activeDiscovery');return;}
    await chrome.storage.local.set({activeDiscovery:{tabId,command}});
    try {
      while(!current.terminal){
        const latest=await chrome.tabs.get(tabId);
        if(!ProductHunterDiscovery.searchPage(latest.url,command.query)){await finish('error');break;}
        const pending=(await chrome.storage.local.get('pendingDiscoveryStep')).pendingDiscoveryStep;
        let payload;
        if(pending?.command_id===command.id)payload=pending.payload;
        else {
          const response=await chrome.tabs.sendMessage(tabId,{type:'PH_DISCOVER_SEARCH_VIEWPORT',options:{command_id:command.id,query:command.query,scroll_iteration:current.next_iteration,document_token:current.document_token}});
          if(response?.stopped){current=await state();break;}
          if(response?.challenge){if(typeof stopForSecurity==='function')await stopForSecurity(response.error||'security_challenge');await finish('security_challenge');break;}
          if(response?.timeout){await finish('timeout');break;}
          if(!response?.ok){await finish('error');break;}
          payload={extension_id:chrome.runtime.id,scroll_iteration:current.next_iteration,document_token:response.document_token,dom_card_count:response.dom_card_count,capture:response.capture,scroll_target:response.scroll_target??null,scroll_before:response.scroll_before??null,scroll_after:response.scroll_after??null};
          await chrome.storage.local.set({pendingDiscoveryStep:{command_id:command.id,payload}});
        }
        current=await request(path+'/step',payload);await chrome.storage.local.remove('pendingDiscoveryStep');
      }
      await chrome.storage.local.remove('activeDiscovery');
    } catch(error) {
      if(/HTTP (404|409)/.test(String(error))){
        const final=await state();

        if(!final.terminal)await finish('error');await chrome.storage.local.remove('activeDiscovery');await chrome.storage.local.remove('pendingDiscoveryStep');
      }
      else {
        const saved=(await chrome.storage.local.get('discoveryTransportFailures')).discoveryTransportFailures||{};
        const attempts=saved.command_id===command.id?saved.attempts+1:1;
        await chrome.storage.local.set({discoveryTransportFailures:{command_id:command.id,attempts}});
        const limit=globalThis.ProductHunterPacing?.settings.transportAttempts||3;
        if(attempts>=limit){await finish('error');await chrome.storage.local.remove('activeDiscovery');await chrome.storage.local.remove('pendingDiscoveryStep');}
        else throw error; // Exact pending viewport survives only bounded transport retries.
      }
    }
  }
  globalThis.ProductHunterDiscoveryWorker={run};
})();
