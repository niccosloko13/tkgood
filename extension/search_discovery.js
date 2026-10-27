/* Dedicated bounded search discovery. No clicks or video navigation. */
(() => {
  'use strict';
  const LIMITS=Object.freeze({maxScrolls:5,maxUnique:30,maxRuntime:90000,stagnantCycles:2,settleMs:1800});
  const token=globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  let active=null;
  const normalizeQuery=value=>String(value??'').normalize('NFKC').trim().replace(/\s+/gu,' ').toLowerCase();
  function searchPage(value,query) {
    try {
      const u=new URL(value),queries=u.searchParams.getAll('q');
      return u.protocol==='https:' && ['www.tiktok.com','tiktok.com'].includes(u.hostname) && !u.port && !u.username && !u.password &&
        u.pathname.replace(/\/$/,'')==='/search' && !!normalizeQuery(query) && queries.length===1 && normalizeQuery(queries[0])===normalizeQuery(query);
    }catch{return false;}
  }
  // Never persist arbitrary params, credentials or fragments (tokens can occur there).
  function routeDiagnostic(expected,value,query) {
    const read=value=>{try{const u=new URL(value);return {url:`${u.protocol}//${u.host}${u.pathname}${u.searchParams.has('q')?'?'+new URLSearchParams({q:u.searchParams.get('q')}).toString():''}`,path:u.pathname,query:normalizeQuery(u.searchParams.get('q'))};}catch{return {url:'[invalid URL]',path:null,query:null};}};
    const e=read(expected),a=read(value);
    return {expected_url:e.url,actual_url:a.url,expected_path:e.path,actual_path:a.path,expected_query:normalizeQuery(query),actual_query:a.query,redirect_chain:null};
  }
  function guard(doc,win,query) {
    if(!searchPage(doc.location.href,query))throw new Error('Discovery search page/query changed');
    globalThis.ProductHunterSafety?.assertSafe(doc);
    const selectors='#captcha-verify-container,[id*="captcha"],[data-e2e*="captcha"],iframe[src*="captcha"],[data-e2e="login-modal"],[role="dialog"] input[type="password"],[role="dialog"] input[autocomplete="one-time-code"]';
    const challenge=[...doc.querySelectorAll(selectors)].some(n=>ProductHunterSearch.visible(n,win));
    if(challenge || /verify (?:that )?you(?: are|'re) human|security verification|complete the captcha/i.test((doc.body?.innerText||'').slice(0,12000))){const e=new Error('Security challenge; human intervention required');e.challenge=true;throw e;}
  }
  function searchScroller(doc,win) {
    const anchors=[...doc.querySelectorAll('a[href*="/video/"]')].filter(a=>ProductHunterSearch.videoUrl(a.getAttribute('href'),doc.location.href)&&ProductHunterSearch.visible(a,win));
    for(const anchor of anchors){
      for(let node=anchor.parentElement;node&&node!==doc.body;node=node.parentElement){
        if(!/(auto|scroll)/.test(win.getComputedStyle(node).overflowY)||node.scrollHeight<=node.clientHeight+1)continue;
        if(node.closest('[role="dialog"],nav,aside,[role="feed"]'))continue;
        const ids=new Set([...node.querySelectorAll('a[href*="/video/"]')].map(a=>ProductHunterSearch.videoUrl(a.getAttribute('href'),doc.location.href)?.split('/').at(-1)).filter(Boolean));
        if(ids.size>=2)return node;
      }
    }
    return doc.scrollingElement;
  }
  async function viewportStep(options,env={}) {
    const doc=env.doc||document,win=env.win||window,sleep=env.sleep||(ms=>new Promise(resolve=>setTimeout(resolve,ms)));
    if(!Number.isInteger(options.command_id)||!Number.isInteger(options.scroll_iteration)||options.scroll_iteration<0||options.scroll_iteration>LIMITS.maxScrolls||typeof options.query!=='string'||options.query.length>200)throw new Error('Invalid bounded discovery step');
    const permit=env.permit||(()=>chrome.runtime.sendMessage({type:'PH_DISCOVERY_PERMISSION',command_id:options.command_id}));
    guard(doc,win,options.query);
    const permission=await permit();
    if(!permission?.allowed){const e=new Error('Discovery stopped');e.stopped=true;throw e;}
    guard(doc,win,options.query);
    if(options.document_token && options.document_token!==token)throw new Error('Discovery document changed');
    if(active?.command_id!==options.command_id){if(options.scroll_iteration!==0)throw new Error('Discovery state lost; refusing another scroll');active={command_id:options.command_id,started:Date.now(),next:0,cache:new Map(),inflight:null};}
    if(active.cache.has(options.scroll_iteration))return active.cache.get(options.scroll_iteration);
    if(active.inflight){if(active.inflight.iteration!==options.scroll_iteration)throw new Error('Discovery already running');return active.inflight.promise;}
    if(options.scroll_iteration!==active.next)throw new Error('Discovery scroll sequence changed');
    if(Date.now()-active.started>=LIMITS.maxRuntime){const e=new Error('Discovery timeout');e.timeout=true;throw e;}
    const operation=(async()=>{
      const root=searchScroller(doc,win),before=Number(root?.scrollTop)||0;
      if(options.scroll_iteration>0){if(!root||typeof root.scrollBy!=='function'||root.scrollHeight<=root.clientHeight+1)throw new Error('Scrollable search-results container unavailable');root.scrollBy({top:Math.max(1,Math.floor((root.clientHeight||win.innerHeight)*.8)),left:0,behavior:'instant'});}
      await sleep(LIMITS.settleMs);guard(doc,win,options.query);
      let items=ProductHunterSearch.extractSearchResults(doc,win),stable=1;
      const pacing=globalThis.ProductHunterPacing?.settings||{pollMs:1000,stableSamples:2,stabilityAttempts:8};
      for(let attempt=1;attempt<pacing.stabilityAttempts;attempt++){
        const signature=JSON.stringify(items.map(v=>[v.video_id,v.caption]));
        await sleep(pacing.pollMs);guard(doc,win,options.query);
        const permission=await permit();if(!permission?.allowed){const e=new Error('Discovery stopped');e.stopped=true;throw e;}
        const next=ProductHunterSearch.extractSearchResults(doc,win);
        stable=JSON.stringify(next.map(v=>[v.video_id,v.caption]))===signature?stable+1:1;items=next;
        if(stable>=pacing.stableSamples)break;
        if(attempt===pacing.stabilityAttempts-1)throw new Error('Search results did not stabilize');
      }
      const results=items.slice(0,LIMITS.maxUnique).map(v=>({...v,card_snapshot:null,raw_visible_text:v.raw_visible_text?.slice(0,2000)||null}));
      const ids=new Set([...doc.querySelectorAll('a[href*="/video/"]')].map(a=>ProductHunterSearch.videoUrl(a.getAttribute('href'),doc.location.href)?.split('/').at(-1)).filter(Boolean));
      const response={capture:{query:options.query,page_url:doc.location.href,results_count:results.length,links_detected:Math.min(10000,items.linksDetected||results.length),results},document_token:token,dom_card_count:Math.min(10000,ids.size),scroll_target:((root?.tagName||'document')+':'+(root?.getAttribute?.('data-e2e')||'')).slice(0,128),scroll_before:before,scroll_after:Number(root?.scrollTop)||0};
      active.cache.set(options.scroll_iteration,response);active.next++;return response;
    })();
    active.inflight={iteration:options.scroll_iteration,promise:operation};
    try{return await operation;}finally{active.inflight=null;}
  }
  const api={LIMITS,searchPage,routeDiagnostic,guard,searchScroller,viewportStep};globalThis.ProductHunterDiscovery=Object.freeze(api);
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})();
