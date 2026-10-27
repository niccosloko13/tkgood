(() => {
  "use strict";
  let securityStopped=false;

  // READ ONLY: the comments sampler may open only its fixed section toggle.
  // This script never submits, follows, likes, comments,
  // shares, saves, publishes, or mutates the TikTok account.

  function textExists(words) {
    const text = (document.body?.innerText || "").toLowerCase();
    return words.some(w => text.includes(w));
  }

  function collectSignals() {
    const text = (document.body?.innerText || "").toLowerCase();

    const session = globalThis.ProductHunterSession?.read(document, location.href) ||
      {current_page_status:'unknown',tiktok_session_status:'unconfirmed',session_evidence:[]};

    return {
      security_stop:globalThis.ProductHunterSafety?.reason(document)??null,
      document_visibility:document.visibilityState??null,
      extension_version: chrome.runtime.getManifest().version,
      ...(globalThis.PH_BUILD_ID ? {companion_version:chrome.runtime.getManifest().version,build_id:globalThis.PH_BUILD_ID} : {}),
      current_url: location.href,
      page_title: document.title ?? null,
      authenticated_hint: session.tiktok_session_status === 'confirmed',
      ...session,
      page_ready_state: document.readyState ?? null,
      has_search_ui: textExists(["pesquisar", "search"]),
      playback_error_visible:
        text.includes("problemas para reproduzir este vídeo") ||
        text.includes("problem playing this video")
    };
  }

  function heartbeat() {
    if(securityStopped)return;
    chrome.runtime.sendMessage({
      type: "PH_HEARTBEAT",
      payload: collectSignals()
    }, response => {if(response?.stopped)securityStopped=true;void chrome.runtime.lastError;});
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if(message?.type==='PH_SECURITY_STOP'&&sender.id===chrome.runtime.id){
      securityStopped=true;globalThis.ProductHunterSafety?.stop(message.reason);sendResponse({ok:true});return;
    }
    if(message?.type?.startsWith('PH_READ_')||message?.type==='PH_DISCOVER_SEARCH_VIEWPORT'){
      const reason=globalThis.ProductHunterSafety?.reason(document);
      if(reason){sendResponse({ok:false,challenge:true,security_stop:reason,error:reason});return;}
    }
    if (message?.type === 'PH_DISCOVER_SEARCH_VIEWPORT') {
      ProductHunterDiscovery.viewportStep(message.options)
        .then(result=>sendResponse({ok:true,...result}))
        .catch(error=>sendResponse({ok:false,error:String(error),stopped:!!error.stopped,challenge:!!error.challenge,timeout:!!error.timeout}));
      return true;
    }
    if (message?.type === "PH_SIGNALS") sendResponse(collectSignals());
    if (message?.type === 'PH_READ_CREATOR_PROFILE') {
      try {
        if(ProductHunterCreator.profileUrl(location.href)!==message.profile_url)throw new Error('Profile identity changed');
        sendResponse({ok:true,...ProductHunterCreator.extractCreatorProfile()});
      } catch(error) {sendResponse({ok:false,error:String(error)});}
    }
    if (message?.type === 'PH_READ_COMMENTS_SAMPLE') {
      ProductHunterComments.sampleComments({video_url:message.video_url,target_count:message.target_count})
        .then(comments_sample=>sendResponse({ok:true,comments_sample}))
        .catch(error=>sendResponse({ok:false,error:String(error),challenge:!!error.challenge||/security challenge/i.test(String(error))}));
      return true;
    }
    if (message?.type === 'PH_READ_VIDEO_DETAIL') {
      try {
        const actual = ProductHunterSearch.videoUrl(location.href, location.href);
        if (actual !== message.video_url) throw new Error('Video route does not match requested identity');
        sendResponse({ok:true, ...ProductHunterDetail.extractVideoDetail()});
      } catch(error) { sendResponse({ok:false, error:String(error)}); }
    }
    if (message?.type === 'PH_READ_SEARCH_RESULTS') {
      try {
        const query = new URL(location.href).searchParams.get('q');
        if (query !== message.query) throw new Error('Search query changed before capture');
        if(message.max_results!==undefined && (!Number.isInteger(message.max_results)||message.max_results<1||message.max_results>10))throw new Error('Invalid bounded capture limit');
        const results = ProductHunterSearch.extractSearchResults(document,window,message.max_results);
        sendResponse({ok: true, diagnostics:{ready_state:document.readyState,document_visibility:document.visibilityState,viewport:[window.innerWidth,window.innerHeight],anchors:[...document.querySelectorAll('a[href*="/video/"]')].slice(0,2).map(a=>{const r=a.getBoundingClientRect();return {visible:ProductHunterSearch.visible(a,window),rect:[r.left,r.top,r.width,r.height],styles:[...(()=>{const nodes=[];for(let n=a;n&&nodes.length<4;n=n.parentElement)nodes.push(n);return nodes;})()].map(n=>{const s=window.getComputedStyle(n);return [n.tagName,n.hidden,s.display,s.visibility,s.opacity];})};}),video_links:document.querySelectorAll('a[href*="/video/"]').length,body_text_length:(document.body?.textContent||'').length}, capture: {query, page_url: location.href,
          results_count: results.length, links_detected: results.linksDetected, invalid_results:results.invalidDetected||0, results}});
      } catch (error) { sendResponse({ok: false, error: String(error)}); }
    }
  });

  heartbeat();
  setInterval(heartbeat, 3000);
})();
