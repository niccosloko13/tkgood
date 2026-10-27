/* Fixed session-only reader installed in an already-open document. No timers. */
(() => {
  if(globalThis.PH_SESSION_OBSERVER)return;
  globalThis.PH_SESSION_OBSERVER=true;
  chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
    if(message?.type!=='PH_SESSION_SIGNALS'||sender.id!==chrome.runtime.id)return;
    const u=new URL(location.href);
    if(u.origin!=='https://www.tiktok.com')return;
    const session=ProductHunterSession.read(document,location.href);
    sendResponse({...session,current_url:location.href,page_title:document.title,page_ready_state:document.readyState,
      document_visibility:document.visibilityState,authenticated_hint:session.tiktok_session_status==='confirmed',
      has_search_ui:Boolean(document.querySelector('[data-e2e="nav-search"],input[type="search"]')),
      playback_error_visible:false,security_stop:session.live_page_blocker});
  });
})();
