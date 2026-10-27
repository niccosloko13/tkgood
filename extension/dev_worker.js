/* Development-only local maintenance. No page clicks or arbitrary navigation. */
(() => {
  'use strict';
  const key = 'pendingDevReload';
  const config = globalThis.PH_DEV;
  const enabled = !!config && config.extension_id === chrome.runtime.id;
  let backendEnabled=true,backendKey=null,pollUnavailable=false;
  let queueStatus=null,queueError=null;
  function setBackendContract(meta){
    const key=JSON.stringify([meta.api_version,meta.dev_control_enabled,meta.backend_run_id]);
    if(key!==backendKey){pollUnavailable=false;backendKey=key;}
    backendEnabled=meta.dev_control_enabled===true && meta.api_version===(globalThis.PH_API_VERSION||'1');
    const installed=chrome.runtime.getManifest?.().version;
    if(installed && meta.companion_min_version){
      const a=installed.split('.').map(Number),b=meta.companion_min_version.split('.').map(Number);
      if(a.some((n,i)=>n!==b[i] && a.slice(0,i).every((v,j)=>v===b[j]) && n<b[i]))backendEnabled=false;
    }
    if(!backendEnabled)chrome.storage.local.set({devControlError:'Backend command API unavailable or incompatible; polling suspended'});
    return backendEnabled;
  }
  const isTikTok = value => {
    try { const u = new URL(value); return u.protocol === 'https:' && u.host === 'www.tiktok.com' && !u.username && !u.password; }
    catch { return false; }
  };
  async function api(path, body) {
    const response = await fetch('http://127.0.0.1:8000/api/dev'+path, {
      ...(body !== undefined ? {method:'POST',body:JSON.stringify(body)} : {}),
      headers:{'Content-Type':'application/json','X-PH-Dev-Token':config.token,'X-Extension-ID':chrome.runtime.id},
      signal:AbortSignal.timeout(5000)
    });
    if(path==='/commands/next'){queueStatus=response.status||(response.ok?200:null);queueError=response.ok?null:'API error: /api/dev/commands/next ['+queueStatus+']';}
    if (!response.ok) {
      const error = new Error('Development backend HTTP '+response.status);
      error.status = response.status;
      throw error;
    }
    return response.json();
  }
  async function persist(pending) { await chrome.storage.local.set({[key]:pending}); }
  async function resume(pending) {
    if (pending.phase === 'awaiting_accept') {
      await api(`/commands/${pending.id}/accept`, {});
      pending.phase = 'accepted';
      await persist(pending);
      if (pending.type === 'DEV_RELOAD_EXTENSION') { chrome.runtime.reload(); return true; }
    }
    if (pending.phase === 'accepted') {
      if(pending.type==='DEV_INSPECT_TIKTOK_SESSION'){
        const options=JSON.parse(pending.options_json||'{}');
        if(!Number.isInteger(options.tab_id)||!isTikTok(options.current_url))throw new Error('Existing TikTok tab required; no navigation');
        const tab=await chrome.tabs.get(options.tab_id);
        if(tab.url!==options.current_url)throw new Error('Session probe tab changed');
        pending.phase='probe_attempted';await persist(pending);
        const result=await chrome.scripting.executeScript({target:{tabId:tab.id,frameIds:[0]},files:['session_probe.js']});
        const current=await chrome.tabs.get(tab.id),probe=result.find(r=>r.frameId===0)?.result;
        if(current.url!==options.current_url||probe?.url!==options.current_url)throw new Error('Document changed during probe');
        pending.completion={status:'SUCCEEDED',build_id:globalThis.PH_BUILD_ID,refreshed_tabs:0,detail:'Read-only DOM session probe; zero navigation or reload',session_probe:probe};
        pending.phase='complete';await persist(pending);
      }
    }
    if(pending.phase==='probe_attempted')throw new Error('Uncertain session probe; not replayed');
    if (pending.phase === 'accepted') {
      if(pending.type==='DEV_RENEW_TIKTOK_SESSION'){
        const incident=(await chrome.storage.local.get('securityStop')).securityStop;
        const expected=JSON.parse(pending.options_json||'{}').incident||{};
        if((incident?.reason||null)!==(expected.reason||null)||(incident?.observed_at||null)!==(expected.observed_at||null))throw new Error('Security incident changed; renew refused');
        const all=(await chrome.tabs.query({url:'https://www.tiktok.com/*'})).filter(t=>isTikTok(t.url));
        const pinned=(await chrome.storage.local.get('tiktokTabId')).tiktokTabId;
        const tab=all.find(t=>t.id===pinned)||all[0];
        let signals=null;
        if(tab){try{signals=await chrome.tabs.sendMessage(tab.id,{type:'PH_SIGNALS'});}catch{}}
        if(signals?.security_stop||['http_403','challenge'].includes(signals?.current_page_status))throw new Error('Current page blocked; renewal stopped without navigation');
        // Persist intent before any browser action. An uncertain creation is never replayed.
        pending.phase='renew_attempted';pending.tabs=tab?[tab.id]:[];await persist(pending);
        if(!tab){
          const created=await chrome.tabs.create({url:'https://www.tiktok.com/',active:true});
          pending.tabs=[created.id];await persist(pending);
          await chrome.storage.local.set({tiktokTabId:created.id});
        }else{
          const u=new URL(tab.url),safeRoute=u.pathname==='/'||u.pathname.replace(/\/$/,'')==='/search';
          if(!safeRoute)await chrome.tabs.update(tab.id,{url:'https://www.tiktok.com/'});
          else if(signals?.build_id!==globalThis.PH_BUILD_ID)await chrome.tabs.reload(tab.id);
        }
      }
    }
    if(pending.phase==='renew_attempted'){
      const currentStop=(await chrome.storage.local.get('securityStop')).securityStop;
      const expected=JSON.parse(pending.options_json||'{}').incident||{};
      if((currentStop?.reason||null)!==(expected.reason||null)||(currentStop?.observed_at||null)!==(expected.observed_at||null))throw new Error('New security incident during renewal; STOP; no retry');
      if(pending.tabs.length!==1)throw new Error('Uncertain renewal outcome; no retry or new tab');
      const tab=await chrome.tabs.get(pending.tabs[0]);
      if(tab.status!=='complete')return true;
      if(!isTikTok(tab.url))throw new Error('Renewal tab changed');
      let signals;try{signals=await chrome.tabs.sendMessage(tab.id,{type:'PH_SIGNALS'});}catch{return true;}
      if(signals?.security_stop||['http_403','challenge'].includes(signals?.current_page_status)){
        if(typeof stopForSecurity==='function')await stopForSecurity(signals.security_stop||signals.current_page_status,true);
        throw new Error('Renewal blocked; security stop retained; no retry');
      }
      if(signals?.page_ready_state!=='complete')return true;
      pending.completion={status:'SUCCEEDED',build_id:globalThis.PH_BUILD_ID,refreshed_tabs:0,
        detail:'Existing Chrome session ready for manual login/check; account '+(signals.tiktok_session_status||'unconfirmed')+'; security stop unchanged'};
      pending.phase='complete';await persist(pending);
    }
    if (pending.phase === 'accepted') {
      // Persist before reload; recheck the current URL of every candidate.
      const all = await chrome.tabs.query({url:'https://www.tiktok.com/*'});
      const pinned=(await chrome.storage.local.get('tiktokTabId')).tiktokTabId;
      const incident=(await chrome.storage.local.get('securityStop')).securityStop;
      const expected=JSON.parse(pending.options_json||'{}').incident||{};
      const sameIncident=(incident?.reason||null)===(expected.reason||null) &&
        (incident?.observed_at||null)===(expected.observed_at||null);
      const failed=(incident?.reason||'').match(/^HTTP 403: (https:\/\/www\.tiktok\.com\/@[\w.]+\/video\/\d+)$/)?.[1];
      const knownFailed=(await chrome.storage.local.get('failedVideoUrls')).failedVideoUrls||[];
      const quarantined=(await chrome.storage.local.get('blockedTargets')).blockedTargets||[];
      const directMode=(await chrome.storage.local.get('directVideoEnrichment')).directVideoEnrichment;
      const directPaused=value=>{try{const path=new URL(value).pathname;return directMode?.status==='PAUSED'&&(/\/video\//.test(path)||/^\/@[^/]+\/?$/.test(path));}catch{return false;}};
      const targetBlocked=value=>{
        const item=globalThis.ProductHunterTargetSafety?.target(value);
        return item&&quarantined.some(x=>['BLOCKED','TEMPORARILY_QUARANTINED'].includes(x.status)&&(x.url===item.url||(item.target_type==='VIDEO'&&x.target_type==='VIDEO'&&x.url.split('/').at(-1)===item.url.split('/').at(-1))));
      };
      if (failed && !knownFailed.includes(failed)) {
        knownFailed.push(failed);
        await chrome.storage.local.set({failedVideoUrls:knownFailed});
      }
      if (pending.type==='DEV_VALIDATE_TIKTOK_HOME' && (!sameIncident || (incident && !failed))) {
        throw new Error('Security incident changed; home recovery refused');
      }
      const safe=all.filter(t=>isTikTok(t.url) && !knownFailed.includes(t.url) && !targetBlocked(t.url) && !directPaused(t.url));
      const selected=pending.type==='DEV_VALIDATE_TIKTOK_HOME'
        ? safe.find(t=>t.id===pinned)||safe[0]||all.find(t=>t.id===pinned)||all.find(t=>isTikTok(t.url))
        : safe.find(t=>t.id===pinned)||safe[0];
      const tabs=selected?[selected]:[];
      pending.tabs = pending.tabs || [];
      for (const tab of tabs) {
        const current = await chrome.tabs.get(tab.id);
        if (!isTikTok(current.url) || pending.tabs.includes(tab.id)) continue;
        if(pending.type!=='DEV_VALIDATE_TIKTOK_HOME'&&targetBlocked(current.url))continue;
        if(directPaused(current.url)&&pending.type!=='DEV_VALIDATE_TIKTOK_HOME')continue;
        // A normal reload never revisits a known failed URL or navigates under a latch.
        if (incident && pending.type!=='DEV_VALIDATE_TIKTOK_HOME') continue;
        // Persist the attempted tab before navigation; an uncertain outcome is not replayed.
        pending.tabs.push(tab.id);
        await persist(pending);
        if (pending.type==='DEV_VALIDATE_TIKTOK_HOME') {
          await chrome.storage.local.set({tiktokTabId:tab.id});
          if (current.url !== 'https://www.tiktok.com/') await chrome.tabs.update(tab.id,{url:'https://www.tiktok.com/'});
          else await chrome.tabs.reload(tab.id);
        } else await chrome.tabs.reload(tab.id);
      }
      pending.phase = 'refreshed';
      await persist(pending);
    }
    if (pending.phase === 'refreshed') {
      for (const id of pending.tabs) {
        const tab = await chrome.tabs.get(id);
        if (!isTikTok(tab.url)) throw new Error('TikTok tab changed during refresh');
        if (tab.status !== 'complete') return true;
        let signals;
        try { signals = await chrome.tabs.sendMessage(id, {type:'PH_SIGNALS'}); } catch { return true; }
        if (signals?.page_ready_state !== 'complete' || signals?.build_id !== globalThis.PH_BUILD_ID) return true;
        if (pending.type==='DEV_VALIDATE_TIKTOK_HOME') {
          const stop=(await chrome.storage.local.get('securityStop')).securityStop;
          const expected=JSON.parse(pending.options_json||'{}').incident||{};
          if ((stop?.reason||null)!==(expected.reason||null) || (stop?.observed_at||null)!==(expected.observed_at||null)) {
            throw new Error('Security incident changed during home validation');
          }
          if (tab.url!=='https://www.tiktok.com/' || signals.security_stop || signals.current_page_status==='http_403' ||
              signals.current_page_status==='challenge' || signals.tiktok_session_status==='login_required') {
            if (tab.url==='https://www.tiktok.com/' && (signals.security_stop || ['http_403','challenge'].includes(signals.current_page_status)) &&
                typeof stopForSecurity==='function') {
              await stopForSecurity(signals.security_stop||'Home validation: '+signals.current_page_status,true);
            }
            throw new Error('Home validation stopped: security, login or navigation changed');
          }
          if (signals.current_page_status!=='healthy' || signals.tiktok_session_status!=='confirmed' ||
              !['visible_own_profile_with_avatar','visible_account_inbox'].every(e=>signals.session_evidence?.includes(e))) return true;
          pending.homeSamples=(pending.homeSamples||0)+1;
          await persist(pending);
          if(pending.homeSamples<2)return true;
        }
      }
      pending.completion = {
        status:globalThis.PH_BUILD_ID === pending.expected_build && (pending.type!=='DEV_VALIDATE_TIKTOK_HOME'||pending.tabs.length===1) ? 'SUCCEEDED' : 'FAILED',
        build_id:globalThis.PH_BUILD_ID,
        refreshed_tabs:pending.tabs.length,
        detail:globalThis.PH_BUILD_ID !== pending.expected_build ? 'Loaded build differs from requested build' :
          pending.type==='DEV_VALIDATE_TIKTOK_HOME' ? 'Home validation finished; security stop retained until explicit operator clearance' :
          pending.tabs.length ? 'Companion ready; existing TikTok tabs refreshed' : 'Worker ready; no tab refreshed (missing tab or active security stop)'
      };
      pending.phase = 'complete';
      await persist(pending);
    }
    await api(`/commands/${pending.id}/complete`,pending.completion);
    await chrome.storage.local.remove(key);
    return true;
  }
  async function tick() {
    if (!enabled || !backendEnabled || pollUnavailable) return false;
    let pending = (await chrome.storage.local.get(key))[key];
    try {
      if (!pending) {
        const {command} = await api('/commands/next');
        if (!command) return false;
        if (!['DEV_RELOAD_EXTENSION','DEV_REFRESH_TIKTOK','DEV_VALIDATE_TIKTOK_HOME','DEV_RENEW_TIKTOK_SESSION','DEV_INSPECT_TIKTOK_SESSION'].includes(command.type) ||
            !/^[a-f0-9]{32}$/.test(command.id) || !/^[a-f0-9]{16}$/.test(command.expected_build) ||
            command.extension_id !== chrome.runtime.id) throw new Error('Invalid development command');
        pending = {...command, phase:'awaiting_accept', tabs:[]};
        await persist(pending);
      }
      if (pending.phase !== 'complete' && Date.now() - Date.parse(pending.created_at) > 55000) {
        pending.phase = 'complete';
        pending.completion = {status:'FAILED',build_id:globalThis.PH_BUILD_ID,
          refreshed_tabs:pending.type==='DEV_RENEW_TIKTOK_SESSION'?0:pending.tabs.length,detail:'Timed out waiting for refreshed TikTok content scripts'};
        await persist(pending);
      }
      return await resume(pending);
    } catch (error) {
      if (error.status === 404 || error.status === 409) {
        if(error.status===404){pollUnavailable=true;await chrome.storage.local.set({devControlError:'Command endpoint unavailable; polling suspended until backend contract changes'});}
        if (pending) await chrome.storage.local.remove(key);
        return false;
      }
      if (pending && !error.status && !/fetch|network|timeout/i.test(String(error))) {
        pending.phase='complete';
        pending.completion={status:'FAILED',build_id:globalThis.PH_BUILD_ID,refreshed_tabs:pending.type==='DEV_RENEW_TIKTOK_SESSION'?0:pending.tabs.length,detail:String(error).slice(0,1000)};
        await persist(pending);
        return true;
      }
      // Retain durable state on transport failure; do not replay page reloads.
      await chrome.storage.local.set({devControlError:String(error)});
      return true;
    }
  }
  globalThis.ProductHunterDev = Object.freeze({tick,setBackendContract,diagnostics:()=>({command_api_status:queueStatus,command_api_error:queueError})});
})();
