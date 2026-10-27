/* Fixed passive session/page samples. No navigation, result reads or retries. */
(() => {
 'use strict';
 async function wait(options,env){
  const {chrome,pacing,assertSafe,stopForSecurity,sleep}=env,now=env.now||(()=>Date.now());
  const started=now(),deadline=Math.min(options.deadlineMs,started+pacing.searchTimeoutMs);
  const samples=options.phase==='PRE_QUERY'?options.diagnostics.pre_health.samples:options.diagnostics.settle_samples;
  let consecutive=0,invalidSince=null;
  const parsed=value=>{try{return new URL(value);}catch{return null;}};
  const general=u=>u&&(u.pathname==='/'||u.pathname.replace(/\/$/,'')==='/search'&&u.searchParams.getAll('q').length===1&&!!u.searchParams.get('q')?.trim());
  const norm=value=>String(value||'').normalize('NFKC').trim().replace(/\s+/gu,' ').toLowerCase();
  const same=(u,v)=>u&&v&&u.pathname.replace(/\/$/,'')===v.pathname.replace(/\/$/,'')&&norm(u.searchParams.get('q'))===norm(v.searchParams.get('q'));
  while(now()<deadline&&samples.length<pacing.queryStabilityMaxSamples){
   await assertSafe();
   const tab=await chrome.tabs.get(options.tabId),u=parsed(tab.url),expected=parsed(options.expectedUrl);
   if(!u||u.protocol!=='https:'||!['www.tiktok.com','tiktok.com'].includes(u.hostname)||u.port||u.username||u.password)throw Error('UNEXPECTED_HOST; no retry');
   if(/^\/(challenge|captcha|verify|login)(\/|$)/i.test(u.pathname)){
    await stopForSecurity('GLOBAL_BLOCK: search stability security/login route',true);throw Error('SECURITY_BLOCK; no retry');
   }
   const valid=general(u)&&same(u,expected);
   const pendingExpected=tab.status==='loading'&&general(u)&&same(parsed(tab.pendingUrl),expected);
   if(!valid&&!pendingExpected){
    invalidSince=invalidSince??now();
    if(now()-invalidSince>=pacing.searchRouteGraceMs)throw Error('SEARCH_ROUTE_INVALID_PERSISTENT; no retry');
   }else invalidSince=null;
   let signals=null;
   // The previous document may disappear during navigation. Only fixed passive
   // diagnostic messages are retried by polling; no card read or navigation is.
   try{signals=await chrome.tabs.sendMessage(options.tabId,{type:'PH_SIGNALS'});}catch{/* TRANSIENT_LOADING */}
   const safety=globalThis.ProductHunterSafetyGate?.observation(signals||{});
   const blocker=String(signals?.security_stop||signals?.error||'');
   if(!safety)throw Error('CANONICAL_SAFETY_CONTRACT_MISSING');
   if(safety.security==='GLOBAL_BLOCKED'&&safety.reason==='SECURITY_BLOCK'){
    await stopForSecurity(blocker||signals?.current_page_status||'search security blocker',true);throw Error('SECURITY_BLOCK; no retry');
   }
   if(safety.page==='LOGGED_OUT'){
    await stopForSecurity('GLOBAL_BLOCK: confirmed logged out during search stability',true);throw Error('LOGGED_OUT; no retry');
   }
   const settled=options.phase==='PRE_QUERY'||now()-started>=pacing.settleMs;
   const documentMatches=!signals?.current_url||same(parsed(signals.current_url),expected);
   const healthy=valid&&documentMatches&&settled&&tab.status==='complete'&&safety.may_continue;
   consecutive=healthy?consecutive+1:0;
   const sample={elapsed_ms:now()-started,tab_status:tab.status||'unknown',ready_state:signals?.page_ready_state||'unknown',page:signals?.current_page_status||'unknown',session:signals?.tiktok_session_status||'unconfirmed',state:healthy?'HEALTHY_CONFIRMED':'TRANSIENT_LOADING',consecutive};
   samples.push(sample);
   if(consecutive>=pacing.stableSamples){
    if(options.phase==='PRE_QUERY')options.diagnostics.pre_health.final_health=sample;
    else options.diagnostics.final_health=sample;
    return {tab,signals};
   }
   await sleep(pacing.pollMs);
  }
  throw Error('SESSION_NOT_STABLE; no retry');
 }
 const api=Object.freeze({wait});globalThis.ProductHunterSearchStability=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})();
