const DASHBOARD = "http://127.0.0.1:8000";
// These generated local files contain no TikTok credentials and are gitignored.
if (typeof importScripts === 'function') {
  try { importScripts('build.js'); } catch { /* Packaged/non-dev installation. */ }
  try { importScripts('dev_config.js'); } catch { /* Development control opt-in. */ }
  importScripts('pacing.js','safety_gate.js','dev_worker.js');
  importScripts('search_discovery.js','discovery_worker.js','target_security.js','search_stability.js');
}
const isTikTok = url => {
  try { const u = new URL(url); return u.protocol === "https:" && u.hostname === "www.tiktok.com"; }
  catch { return false; }
};
let running = false;
function canonicalVideo(url) {
  try {
    const u = new URL(url);
    if (u.protocol !== 'https:' || u.host !== 'www.tiktok.com' || u.username || u.password || !/^\/@[A-Za-z0-9._]+\/video\/[0-9]+\/?$/.test(u.pathname)) return null;
    return u.origin + u.pathname.replace(/\/$/, '');
  } catch { return null; }
}
const pacing=ProductHunterPacing.settings;
globalThis.ProductHunterDirectMode=Object.freeze({async assertAllowed(value=null){
  if(value){let path;try{path=new URL(value).pathname;}catch{throw Error('Invalid navigation URL');}
    if(!/\/(?:video)\//.test(path)&&!/^\/@[^/]+\/?$/.test(path))return;
  }
  const mode=(await chrome.storage.local.get('directVideoEnrichment')).directVideoEnrichment;
  if(mode?.status==='PAUSED')throw Error('DIRECT_VIDEO_ENRICHMENT_PAUSED');
}});
globalThis.PH_TARGET_SAFETY=globalThis.ProductHunterTargetSafety?.create({chrome,request,stopForSecurity});
async function assertSafe() {
  const state=(await chrome.storage.local.get('securityStop')).securityStop;
  if(state){const e=new Error('Security stop: '+state.reason);e.challenge=true;throw e;}
  if(await globalThis.PH_TARGET_SAFETY?.isHolding())throw new Error('Target HTTP 403: waiting for passive healthy home/search');
}
async function stopForSecurity(reason, freshIncident=false) {
  const previous=(await chrome.storage.local.get('securityStop')).securityStop;
  if(previous && !freshIncident)return;
  const record={reason:String(reason).slice(0,500),observed_at:new Date().toISOString()};
  const failed=record.reason.match(/^HTTP 403: (https:\/\/www\.tiktok\.com\/@[\w.]+\/video\/\d+)$/)?.[1];
  if(failed){
    const urls=(await chrome.storage.local.get('failedVideoUrls')).failedVideoUrls||[];
    if(!urls.includes(failed))await chrome.storage.local.set({failedVideoUrls:[...urls,failed]});
  }
  await chrome.storage.local.set({securityStop:record});
  const tabId=(await chrome.storage.local.get('tiktokTabId')).tiktokTabId;
  if(tabId!==undefined){try{await chrome.tabs.sendMessage(tabId,{type:'PH_SECURITY_STOP',reason:record.reason});}catch{/* Page may already be gone. */}}
  await request('/api/bridge/security-stop',{extension_id:chrome.runtime.id,...record});
}
async function updateTab(id,properties) {
  if(properties.url)await globalThis.ProductHunterDirectMode?.assertAllowed(properties.url);
  await assertSafe();
  if(properties.url)await globalThis.PH_TARGET_SAFETY?.assertAllowed(properties.url);
  const tab=await chrome.tabs.get(id);
  if(properties.url && properties.url!==tab.url){
    await ProductHunterPacing.sleep(pacing.cooldownMs);
    await globalThis.ProductHunterDirectMode?.assertAllowed(properties.url);
    // A 403 may arrive during cooldown; recheck immediately before the open.
    await globalThis.PH_TARGET_SAFETY?.assertAllowed(properties.url);
    await assertSafe();
    return chrome.tabs.update(id,{url:properties.url});
  }
  return tab;
}
async function prepareExistingTab(tab) {
  await assertSafe();
  // One normal browser action per explicit command, never a visibility retry.
  if(chrome.windows&&tab.windowId!==undefined){
    const current=await chrome.windows.get(tab.windowId);
    if(current.state==='minimized')await chrome.windows.update(tab.windowId,{state:'normal'});
  }
  if(tab.active===false)await chrome.tabs.update(tab.id,{active:true});
}
async function readMessage(id,message) {
  await assertSafe();
  let response;
  for(let attempt=0;attempt<pacing.transportAttempts;attempt++){
    try {response=await chrome.tabs.sendMessage(id,message);break;}
    catch(error){if(attempt===pacing.transportAttempts-1)throw error;await ProductHunterPacing.sleep(pacing.pollMs);}
  }
  const failure=response?.security_stop||response?.error||'';
  if(/403|access.denied/i.test(failure)&&!/captcha|challenge|verify.*human/i.test(failure)&&!response?.diagnostics?.captcha_present){
    const tab=await chrome.tabs.get(id);
    if(globalThis.ProductHunterTargetSafety?.target(tab.url)){
      const known=(await chrome.storage.local.get('blockedTargets')).blockedTargets||[];
      if(known.some(x=>x.url===globalThis.ProductHunterTargetSafety.target(tab.url).url))throw new Error('TARGET_PREVIOUSLY_BLOCKED');
      await globalThis.PH_TARGET_SAFETY.http403(tab.url);throw new Error('TARGET_HTTP_403_QUARANTINED; waiting for passive home/search health');
    }
  }
  if(response?.challenge || response?.security_stop || response?.diagnostics?.captcha_present || /403|access.denied|captcha|challenge|verify.*human/i.test(response?.error||'')){
    await stopForSecurity(response.security_stop||response.error||'security_challenge');
    const error=new Error('Security challenge; human intervention required');error.challenge=true;throw error;
  }
  return response;
}
async function readSearch(tabId,query) {
  const deadline=Date.now()+pacing.searchTimeoutMs;let previous=null,stable=0,diagnostic='No response';
  while(Date.now()<deadline){
    await ProductHunterPacing.sleep(pacing.pollMs);
    const tab=await chrome.tabs.get(tabId);
    if(!ProductHunterDiscovery.searchPage(tab.url,query))throw new Error('Search navigation changed');
    if(tab.status!=='complete')continue;
    const response=await readMessage(tabId,{type:'PH_READ_SEARCH_RESULTS',query});
    diagnostic=JSON.stringify({ok:response?.ok,error:response?.error,count:response?.capture?.results_count,diagnostics:response?.diagnostics});
    if(!response?.ok||!response.capture?.results_count)continue;
    const signature=JSON.stringify(response.capture.results.map(v=>[v.video_id,v.caption]));
    stable=signature===previous?stable+1:1;previous=signature;
    if(stable>=pacing.stableSamples)return response.capture;
  }
  throw new Error('Search data did not become ready and stable; no refresh attempted; '+diagnostic.slice(0,600));
}
async function readBoundedSearch(tabId,query,maxResults,initialUrl=null,deadlineAt=null,strictHealth=false,stableObservation=null) {
  const deadline=Math.min(Date.now()+pacing.searchTimeoutMs,deadlineAt?Date.parse(deadlineAt):Infinity);
  let healthySamples=0,healthSamples=0;
  const expected=new URL('https://www.tiktok.com/search');expected.searchParams.set('q',query);
  async function recordRoute(url) {
    const route=ProductHunterDiscovery.routeDiagnostic(expected.href,url,query);
    await chrome.storage.local.set({safeSearchRouteDiagnostic:route});
    return route;
  }
  while(Date.now()<deadline){
    await assertSafe();
    const tab=await chrome.tabs.get(tabId);
    const route=await recordRoute(tab.url);
    if(!ProductHunterDiscovery.searchPage(tab.url,query)){
      // tabs.update resolves before the new document commits. Only tolerate the
      // bound starting document while Chrome explicitly reports our pending URL.
      if(tab.status==='loading' && tab.url===initialUrl && ProductHunterDiscovery.searchPage(tab.pendingUrl,query)){
        await ProductHunterPacing.sleep(pacing.pollMs);continue;
      }
      if(/^\/(challenge|captcha|verify)(\/|$)/i.test(route.actual_path||''))await stopForSecurity('Security search redirect: '+route.actual_path,true);
      throw new Error('Safe search route changed; '+JSON.stringify(route));
    }
    if(tab.status!=='complete'){await ProductHunterPacing.sleep(pacing.pollMs);continue;}
    const signals=stableObservation?.signals||await chrome.tabs.sendMessage(tabId,{type:'PH_SIGNALS'});
    const safety=globalThis.ProductHunterSafetyGate?.observation(signals||{});
    if(!safety)throw new Error('CANONICAL_SAFETY_CONTRACT_MISSING');
    if(safety.security==='GLOBAL_BLOCKED'&&safety.reason==='SECURITY_BLOCK'){
      await stopForSecurity(signals.security_stop||signals.current_page_status,true);
      throw new Error('Security block; no retry');
    }
    if(safety.page==='LOGGED_OUT'){
      await stopForSecurity('GLOBAL_BLOCK: search session degraded/login required',true);
      throw new Error('Security block; no retry');
    }
    healthSamples++;
    const healthy=safety.may_continue;
    if(strictHealth&&!healthy)throw new Error('Stage 2 session/page not healthy; stopped without retry');
    healthySamples=healthy?(stableObservation?pacing.stableSamples:healthySamples+1):0;
    const readiness={page:signals?.current_page_status??'unknown',session:signals?.tiktok_session_status??'unconfirmed',ready_state:signals?.page_ready_state??null,samples:healthSamples,healthy_samples:healthySamples};
    await chrome.storage.local.set({safeSearchReadinessDiagnostic:readiness});
    if(healthySamples<pacing.stableSamples){
      if(healthSamples>=pacing.stabilityAttempts)throw new Error('UNKNOWN/unstable search health; capture refused; '+JSON.stringify(readiness));
      await ProductHunterPacing.sleep(pacing.pollMs);continue;
    }
    // Exactly one card read; no scrolling, readiness recapture or transport retry.
    if(Date.now()>=deadline)throw new Error('Bounded search runtime reached; no retry');
    const response=await chrome.tabs.sendMessage(tabId,{type:'PH_READ_SEARCH_RESULTS',query,max_results:maxResults});
    if(response?.challenge||response?.security_stop||/403|access.denied|captcha|challenge|verify.*human/i.test(response?.error||'')){
      await stopForSecurity(response.security_stop||response.error||'Security challenge',true);
      throw new Error('Security block; no retry');
    }
    if(!response?.ok||!response.capture?.results_count)throw new Error('Empty/unavailable viewport; stopped without retry');
    if(response.capture.results_count>maxResults||response.capture.links_detected>maxResults)throw new Error('Bounded viewport exceeded hard limit');
    const finalTab=await chrome.tabs.get(tabId);
    if(!ProductHunterDiscovery.searchPage(finalTab.url,query)||!ProductHunterDiscovery.searchPage(response.capture.page_url,query)){
      const finalRoute=await recordRoute(finalTab.url);
      if(/^\/(challenge|captcha|verify)(\/|$)/i.test(finalRoute.actual_path||''))await stopForSecurity('Security search redirect: '+finalRoute.actual_path,true);
      throw new Error('Safe search route changed during capture; '+JSON.stringify(finalRoute));
    }
    await assertSafe();
    const heartbeat=await request('/api/bridge/heartbeat',{...signals,...(globalThis.PH_API_VERSION?{api_version:globalThis.PH_API_VERSION}:{}),safe_collection_version:'v1',tab_id:tabId,current_url:tab.url,tiktok_tab_count:1},{'X-Extension-ID':chrome.runtime.id});
    if(heartbeat.security_stop?.reason){await stopForSecurity(heartbeat.security_stop.reason);throw new Error('Security stop persisted before capture completion');}
    return response.capture;
  }
  throw new Error('Bounded search runtime reached; no retry');
}
async function readVideoDetail(tabId, target) {
  await globalThis.ProductHunterDirectMode?.assertAllowed();
  const url = canonicalVideo(target);
  if (!url) throw new Error('Invalid public video URL');
  await globalThis.PH_TARGET_SAFETY?.assertAllowed(url);
  const before = await chrome.tabs.get(tabId);
  const existing = canonicalVideo(before.url);
  // A diagnostic reread of the current video must not restart its async load.
  await updateTab(tabId, existing?.split('/').at(-1)===url.split('/').at(-1) ? {active:true} : {url,active:true});
  const opened = Date.now(), deadline = opened + pacing.readTimeoutMs;
  const identity = url.split('/').at(-1);
  let diagnostic = 'No content-script response';
  let latest = null, latestAt = 0, signature = null;
  while (Date.now() < deadline) {
    await new Promise(resolve => setTimeout(resolve, pacing.pollMs));
    const tab = await chrome.tabs.get(tabId);
    const actual = canonicalVideo(tab.url);
    if (!actual || actual.split('/').at(-1) !== identity) {
      if (Date.now() - opened < 3000) continue;
      throw new Error('Video navigation changed; no data read');
    }
    if (tab.status !== 'complete' || Date.now() - opened < 2000) continue;
    try {
      const response = await readMessage(tabId, {type:'PH_READ_VIDEO_DETAIL', video_url:actual});

      diagnostic = response?.ok ? JSON.stringify(response.diagnostics || {ready:response.ready}) : String(response?.error || 'Empty content-script response');
      if (response?.diagnostics?.captcha_present) {
        latest=null;
        const error=new Error('Security challenge visible; human intervention required');
        error.challenge=true;
        throw error;
      }
      if (response?.ok && response.ready && response.video_detail?.video_url === actual && response.video_detail?.video_id === identity) {
        latest=response.video_detail; latestAt=Date.now();
        const likes=latest.field_evidence?.likes?.value, comments=latest.field_evidence?.comments_count?.value;
        const nextSignature=JSON.stringify([likes,comments]);
        if (Number.isSafeInteger(likes) && Number.isSafeInteger(comments) && signature===nextSignature) return latest;
        signature=nextSignature;
      }
    } catch (error) { throw error; }
  }
  // Metadata-only layouts may expose labels without numbers. Wait the full
  // bounded load window before preserving a fresh partial read with nulls.
  if (latest && Date.now()-latestAt<1500) return latest;
  throw new Error('Video metadata did not become ready within 25 seconds; ' + diagnostic.slice(0,700));
}
async function request(path, body, headers = {}) {
  const response = await fetch(DASHBOARD + path, {
    ...(body ? {method: "POST", headers: {"Content-Type": "application/json", ...headers}, body: JSON.stringify(body)} : {}),
    signal: AbortSignal.timeout(5000)
  });
  if (!response.ok) throw new Error(`Backend HTTP ${response.status}`);
  return response.json();
}
async function readCommentsSample(tabId,target,targetCount) {
  await globalThis.ProductHunterDirectMode?.assertAllowed();
  const url=canonicalVideo(target);
  if(!url || !Number.isInteger(targetCount) || targetCount<1 || targetCount>100) throw new Error('Invalid bounded comments request');
  await globalThis.PH_TARGET_SAFETY?.assertAllowed(url);
  const before=await chrome.tabs.get(tabId);

  await updateTab(tabId,canonicalVideo(before.url)?.split('/').at(-1)===url.split('/').at(-1)?{active:true}:{url,active:true});
  const opened=Date.now(),deadline=opened+20000;let diagnostic='Document not ready';
  while(Date.now()<deadline) {
    await new Promise(resolve=>setTimeout(resolve,pacing.pollMs));
    const tab=await chrome.tabs.get(tabId),actual=canonicalVideo(tab.url);
    if(!actual || actual.split('/').at(-1)!==url.split('/').at(-1)) {
      if(Date.now()-opened<3000) continue;
      throw new Error('Comments video navigation changed');
    }
    if(tab.status!=='complete') continue;
    let response;
    try { response=await readMessage(tabId,{type:'PH_READ_COMMENTS_SAMPLE',video_url:actual,target_count:targetCount}); }
    catch(error) { if(error.challenge)throw error;throw error; }
    if(!response?.ok || !response.comments_sample) throw new Error(response?.error||'No comments sample received');
    return response.comments_sample;
  }
  throw new Error('Comments page preparation timed out: '+diagnostic);
}
function canonicalProfile(value) {
  try {const u=new URL(value);if(u.protocol!=='https:'||u.host!=='www.tiktok.com'||u.username||u.password||!/^\/@[A-Za-z0-9._]{1,128}$/.test(u.pathname))return null;
    return u.origin+u.pathname.toLowerCase();}catch{return null;}
}
async function readCreatorProfile(tabId,target,returnVideo) {
  await globalThis.ProductHunterDirectMode?.assertAllowed();
  const url=canonicalProfile(target),back=canonicalVideo(returnVideo);
  if(!url||!back)throw new Error('Invalid bounded creator profile request');
  await globalThis.PH_TARGET_SAFETY?.assertAllowed(url);
  await globalThis.PH_TARGET_SAFETY?.assertAllowed(back);
  const before=await chrome.tabs.get(tabId);

  await updateTab(tabId,canonicalProfile(before.url)===url?{active:true}:{url,active:true});
  const opened=Date.now(),deadline=opened+pacing.readTimeoutMs;
  let latest=null,signature=null,diagnostic='Waiting for visible profile metadata',challenge=false;
  try {
    while(Date.now()<deadline){
      await new Promise(resolve=>setTimeout(resolve,pacing.pollMs));
      const tab=await chrome.tabs.get(tabId);
      if(canonicalProfile(tab.url)!==url){if(Date.now()-opened<3000)continue;throw new Error('Creator profile navigation changed');}
      if(tab.status!=='complete'||Date.now()-opened<2000)continue;
      let response;try{response=await readMessage(tabId,{type:'PH_READ_CREATOR_PROFILE',profile_url:url});}
      catch(error){if(error.challenge)challenge=true;throw error;}
      if(response?.challenge){challenge=true;throw new Error('Visible profile login/security challenge; human intervention required');}
      diagnostic=JSON.stringify(response?.diagnostics||response?.error||'No response').slice(0,700);
      if(!response?.ok||!response.ready||response.creator_profile?.profile_url!==url)continue;
      latest=response.creator_profile;
      const next=JSON.stringify([latest.followers,latest.total_likes,latest.display_name,latest.bio]);
      if(Date.now()-opened>=5000&&latest.followers!==null&&latest.total_likes!==null&&next===signature)return latest;
      signature=next;
    }
    if(latest)return latest;
    throw new Error('Profile metadata not ready within 25 seconds; '+diagnostic);
  } finally {
    // Return only while still on this command's profile; never override a manual navigation.
    const tab=await chrome.tabs.get(tabId);
    if(!challenge&&canonicalProfile(tab.url)===url){await updateTab(tabId,{url:back,active:true});}
  }
}
async function tick() {
  if (running) return;
  running = true;
  try {
    const tabs = (await chrome.tabs.query({url: "https://www.tiktok.com/*"})).filter(t => isTikTok(t.url));
    tabs.sort((a, b) => Number(b.active) - Number(a.active) || (b.lastAccessed || 0) - (a.lastAccessed || 0));
    const pinned=(await chrome.storage.local.get('tiktokTabId')).tiktokTabId;
    let tab=tabs.find(t=>t.id===pinned)||tabs[0];
    if(tab)await chrome.storage.local.set({tiktokTabId:tab.id});
    let signals = null;
    const localStop=(await chrome.storage.local.get('securityStop')).securityStop;
    // PH_SIGNALS is observation only; a latch blocks readers, not diagnostics.
    if (tab) {
      if(chrome.scripting){
      try {
        signals=await chrome.tabs.sendMessage(tab.id,{type:'PH_SESSION_SIGNALS'});
        if(!signals && chrome.scripting){
          await chrome.scripting.executeScript({target:{tabId:tab.id,frameIds:[0]},files:['session_signals.js','session_observer.js']});
          signals=await chrome.tabs.sendMessage(tab.id,{type:'PH_SESSION_SIGNALS'});
        }
      } catch {
        if(chrome.scripting){try{
          await chrome.scripting.executeScript({target:{tabId:tab.id,frameIds:[0]},files:['session_signals.js','session_observer.js']});
          signals=await chrome.tabs.sendMessage(tab.id,{type:'PH_SESSION_SIGNALS'});
        }catch{/* Unavailable DOM stays unknown; never reload or navigate. */}}
      }
      }
      // Older packaged workers/tests without scripting retain their passive reader.
      if(!signals){try{signals=await chrome.tabs.sendMessage(tab.id,{type:'PH_SIGNALS'});}catch{}}
    }
    const windowInfo=chrome.windows&&tab?.windowId!==undefined?await chrome.windows.get(tab.windowId):{};
    const isolatedDenial=globalThis.ProductHunterTargetSafety?.target(tab?.url)&&/403|access.denied/i.test(signals?.security_stop||'')&&!/captcha|challenge|verify.*human/i.test(signals?.security_stop||'');
    const payload = {
      extension_version: chrome.runtime.getManifest().version,
      ...(globalThis.PH_BUILD_ID ? {companion_version:chrome.runtime.getManifest().version,build_id:globalThis.PH_BUILD_ID,safe_collection_version:'v1',...(globalThis.PH_API_VERSION?{api_version:globalThis.PH_API_VERSION}:{}),...globalThis.ProductHunterDev?.diagnostics?.()} : {}),
      current_url: tab?.url || "",
      tab_id:tab?.id??null, window_id:tab?.windowId??null, tiktok_tab_count:tabs.length,
      document_visibility:signals?.document_visibility??null, security_stop:localStop?.reason||(isolatedDenial?null:signals?.security_stop)||null,
      security_stop_observed_at:localStop?.observed_at||null,
      window_state:windowInfo.state??null,window_width:windowInfo.width??null,
      window_height:windowInfo.height??null,tab_active:tab?.active??null,
      page_title: tab?.title ?? null,
      authenticated_hint: !!signals?.authenticated_hint,
      page_ready_state: signals?.page_ready_state ?? null,
      has_search_ui: !!signals?.has_search_ui,
      playback_error_visible: !!signals?.playback_error_visible,
      current_page_status: signals?.current_page_status || 'unknown',
      tiktok_session_status: signals?.tiktok_session_status || 'unconfirmed',
      session_evidence: signals?.session_evidence || [],
      ...(signals?.session_signals?{session_signals:signals.session_signals,session_debug:signals.session_debug,session_auth_groups:signals.session_auth_groups||[],session_detector_version:signals.session_detector_version}: {})
    };
    const heartbeat=await request("/api/bridge/heartbeat",payload,{"X-Extension-ID":chrome.runtime.id});
    if(heartbeat.direct_video_enrichment)await chrome.storage.local.set({directVideoEnrichment:heartbeat.direct_video_enrichment});
    await globalThis.PH_TARGET_SAFETY?.sync(heartbeat);
    const currentStop=(await chrome.storage.local.get('securityStop')).securityStop;
    if(heartbeat.security_stop?.reason && (!currentStop ||
        Date.parse(heartbeat.security_stop.observed_at)>=Date.parse(currentStop.observed_at))) {
      await chrome.storage.local.set({securityStop:heartbeat.security_stop});
    }
    if (!heartbeat.security_stop?.reason && localStop && currentStop?.observed_at===localStop.observed_at && heartbeat.security_clearance &&
        heartbeat.security_clearance.reason === localStop.reason &&
        heartbeat.security_clearance.observed_at === localStop.observed_at) {
      await chrome.storage.local.remove('securityStop');
    }
    if(heartbeat.browser_open_request&&!heartbeat.security_stop){
      const last=(await chrome.storage.local.get('lastBrowserOpen')).lastBrowserOpen;
      if(last!==heartbeat.browser_open_request.id){
        const failed=(await chrome.storage.local.get('failedVideoUrls')).failedVideoUrls||[];
        const existing=(await chrome.tabs.query({url:'https://www.tiktok.com/*'})).filter(t=>isTikTok(t.url||t.pendingUrl));
        const safe=existing.filter(t=>!failed.includes(t.url));
        tab=safe.find(t=>t.id===tab?.id)||safe[0]||tab||existing[0];
        if(tab && failed.includes(tab.url))tab=await updateTab(tab.id,{url:'https://www.tiktok.com/'});
        if(!tab)tab=await chrome.tabs.create({url:'https://www.tiktok.com/'});
        await chrome.storage.local.set({tiktokTabId:tab.id,lastBrowserOpen:heartbeat.browser_open_request.id});
      }
    }
    await chrome.storage.local.set({bridgeStatus: {...payload, version: payload.extension_version,
      chrome_connected: true, tiktok_open: !!tab, url: payload.current_url, title: payload.page_title,
      page_signals: {content_script_connected: payload.page_ready_state !== null},
      backend_connected: true, last_seen: new Date().toISOString(), error: ""}});
    const {pendingResult} = await chrome.storage.local.get("pendingResult");
    if (pendingResult) {
      if(!['SUCCEEDED','FAILED'].includes(pendingResult.body.status)){
        pendingResult.body={extension_id:chrome.runtime.id,status:'FAILED',detail:'Retired paused operation; submit a new explicit command'};
      }
      try { await request(`/api/bridge/commands/${pendingResult.id}/result`, pendingResult.body); }
      catch (err) { if (!/HTTP (404|409)/.test(String(err))) throw err; }
      await chrome.storage.local.remove("pendingResult");
      await chrome.storage.local.set({lastCommandFinished:Date.now()});
    }
    if(isolatedDenial){
      const known=(await chrome.storage.local.get('blockedTargets')).blockedTargets||[];
      if(!known.some(x=>x.url===globalThis.ProductHunterTargetSafety.target(tab.url)?.url))await globalThis.PH_TARGET_SAFETY.http403(tab.url);
    }else if(signals?.security_stop)await stopForSecurity(signals.security_stop);
    if(globalThis.ProductHunterDev?.setBackendContract?.(heartbeat)===false)return;
    if (globalThis.ProductHunterDev && await ProductHunterDev.tick()) return;
    await globalThis.PH_TARGET_SAFETY?.flush();
    if(await globalThis.PH_TARGET_SAFETY?.isHolding())return;
    if((await chrome.storage.local.get('securityStop')).securityStop)return;
    const {activeDiscovery}=await chrome.storage.local.get('activeDiscovery');
    if(activeDiscovery){await ProductHunterDiscoveryWorker.run(activeDiscovery.tabId,activeDiscovery.command);return;}
    const {command} = await request(`/api/bridge/commands/next?extension_id=${encodeURIComponent(chrome.runtime.id)}`);
    if (command) {
      const last=(await chrome.storage.local.get('lastCommandFinished')).lastCommandFinished||0;
      await ProductHunterPacing.sleep(Math.max(0,pacing.cooldownMs-(Date.now()-last)));
      let status = "FAILED", detail = "Unsupported command", capture = null, video_detail = null, comments_sample = null, creator_profile = null, search_diagnostics=null;
      try {
        if(['READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE'].includes(command.type))await globalThis.ProductHunterDirectMode?.assertAllowed();
        if (!['SEARCH', 'READ_SEARCH_RESULTS', 'READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE','DISCOVER_MORE_RESULTS'].includes(command.type) || typeof command.query !== "string" || !command.query.trim() || command.query.length > (['READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE'].includes(command.type) ? 2048 : 200)) throw new Error("Invalid read-only command");
        if (!tab) throw new Error("TikTok tab is no longer open");
        const current = await chrome.tabs.get(tab.id);
        if (!isTikTok(current.url)) throw new Error("Target tab is no longer TikTok");
        await prepareExistingTab(current);
        if(command.type==='DISCOVER_MORE_RESULTS'){await ProductHunterDiscoveryWorker.run(tab.id,command);return;}
        if (command.type === 'READ_CREATOR_PROFILE') {
          const options=JSON.parse(command.options_json||'{}');
          creator_profile=await readCreatorProfile(tab.id,command.query,options.video_url);
          status='SUCCEEDED';detail='Visible creator profile stored; returned to library video; no engagement';
        } else if (command.type === 'READ_COMMENTS_SAMPLE') {
          const options=JSON.parse(command.options_json||'{}');
          comments_sample=await readCommentsSample(tab.id,command.query,options.target_count??30);
          status='SUCCEEDED';detail=`${comments_sample.comments.length} comments sampled; ${comments_sample.stop_reason}; no engagement`;
        } else if (command.type === 'READ_VIDEO_DETAIL') {
          video_detail = await readVideoDetail(tab.id, command.query);
          status = 'SUCCEEDED'; detail = 'Visible video metadata read (READ ONLY, no engagement)';
        } else if (command.type === 'READ_SEARCH_RESULTS') {
          const options=JSON.parse(command.options_json||'{}');
          if(options.safe_collection_id||options.mission_contract_id){
            if(options.expected_tab_id!==tab.id||current.url!==options.validated_url||options.max_scrolls!==0||!Number.isInteger(options.max_results)||options.max_results<1||options.max_results>10)throw new Error('Safe collection binding or hard limit invalid');
            const target=new URL('https://www.tiktok.com/search');target.searchParams.set('q',command.query);
            let stableObservation=null,deadlineAt=options.deadline_at;
            if(options.strict_health===true){
              search_diagnostics={query:command.query,pre_health:{samples:[]},navigation_state:'NOT_STARTED',settle_samples:[],final_health:null,stop_reason:null};
              const deadlineMs=Math.min(Date.now()+pacing.searchTimeoutMs,options.deadline_at?Date.parse(options.deadline_at):Infinity);
              deadlineAt=new Date(deadlineMs).toISOString();
              const env={chrome,pacing,assertSafe,stopForSecurity,sleep:ProductHunterPacing.sleep};
              await ProductHunterSearchStability.wait({tabId:tab.id,expectedUrl:current.url,phase:'PRE_QUERY',deadlineMs,diagnostics:search_diagnostics},env);
              if(deadlineMs-Date.now()<pacing.cooldownMs+pacing.settleMs+2*pacing.pollMs)throw Error('SESSION_NOT_STABLE; insufficient bounded navigation time');
              search_diagnostics.navigation_state='REQUESTED';
              await updateTab(tab.id,{url:target.href,active:true});
              search_diagnostics.navigation_state='SETTLING';
              stableObservation=await ProductHunterSearchStability.wait({tabId:tab.id,expectedUrl:target.href,phase:'POST_NAVIGATION',deadlineMs,diagnostics:search_diagnostics},env);
            }else{
            await updateTab(tab.id,{url:target.href});
            }
            capture=await readBoundedSearch(tab.id,command.query,options.max_results,current.url,deadlineAt,options.strict_health===true,stableObservation);
            if(search_diagnostics){search_diagnostics.navigation_state='CAPTURED';search_diagnostics.stop_reason='CAPTURE_COMPLETED';}
            status='SUCCEEDED';detail='Single bounded viewport captured; STOP; zero scroll or engagement; '+JSON.stringify((await chrome.storage.local.get('safeSearchRouteDiagnostic')).safeSearchRouteDiagnostic);
          } else {
          const page = new URL(current.url);
          if (page.pathname.replace(/\/$/, '') !== '/search' || page.searchParams.get('q') !== command.query) throw new Error('Search page changed before capture');
          const response = {ok:true,capture:await readSearch(tab.id,command.query)};
          if (!response?.ok || !response.capture) throw new Error(response?.error || 'Reload the TikTok tab to enable capture');
          capture = response.capture;
          status = 'SUCCEEDED'; detail = `${capture.results_count} visible unique results read`;
          }
        } else {
          const target = new URL("https://www.tiktok.com/search");
          target.searchParams.set("q", command.query);
          await updateTab(tab.id, {url: target.href, active: true});
          await readSearch(tab.id,command.query);
          status = "SUCCEEDED"; detail = `Search DOM ready and stable: ${target.href}`;
        }
      } catch (err) {if(err.challenge)await stopForSecurity(String(err));detail=String(err).slice(0,1000);if(search_diagnostics)search_diagnostics.stop_reason=detail;}
      const body = {extension_id: chrome.runtime.id, status, detail};
      if(search_diagnostics)body.search_diagnostics=search_diagnostics;
      if (capture !== null) body.capture = capture;
      if (video_detail !== null) body.video_detail = video_detail;
      if (comments_sample !== null) body.comments_sample = comments_sample;
      if (creator_profile !== null) body.creator_profile = creator_profile;
      await chrome.storage.local.set({pendingResult: {id: command.id, body}});
      await request(`/api/bridge/commands/${command.id}/result`, body);
      await chrome.storage.local.remove("pendingResult");
      await chrome.storage.local.set({lastCommandFinished:Date.now()});
    }
  } catch (err) {
    await chrome.storage.local.set({bridgeStatus: {backend_connected: false, error: String(err), last_seen: new Date().toISOString()}});
  } finally { running = false; }
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if(message?.type==='PH_DISCOVERY_PERMISSION'&&isTikTok(sender.tab?.url)){
    (async()=>{
      const current=await request(`/api/bridge/discovery/${message.command_id}/control?extension_id=${encodeURIComponent(chrome.runtime.id)}`);
      const active=(await chrome.storage.local.get('activeDiscovery')).activeDiscovery;
      return {allowed:!!active&&active.command.id===message.command_id&&active.tabId===sender.tab.id&&!current.terminal&&current.command_status==='DISPATCHED'};
    })().then(sendResponse).catch(()=>sendResponse({allowed:false}));return true;
  }

  if (message?.type === "PH_HEARTBEAT" && isTikTok(sender.tab?.url)) {
    tick().then(()=>chrome.storage.local.get('securityStop')).then(state=>sendResponse({ok:true,stopped:!!state.securityStop})); return true;
  }
  if (message?.type === "PH_REFRESH" && !sender.tab && sender.id === chrome.runtime.id) {
    tick().then(() => sendResponse({ok: true})); return true;
  }
});
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === "ph-heartbeat") tick(); });
async function setup() {
  await chrome.alarms.create("ph-heartbeat", {periodInMinutes: 0.5}); tick();
}
chrome.runtime.onInstalled.addListener(setup);
chrome.runtime.onStartup.addListener(setup);
chrome.tabs.onRemoved.addListener(() => tick());
chrome.tabs.onUpdated.addListener((id, change, tab) => { if (isTikTok(tab.url) && (change.status || change.url)) tick(); });
setInterval(tick, 3000);
setup();

// Observe actual HTTP status; never retry navigation on a security response.
if(chrome.webRequest?.onCompleted)chrome.webRequest.onCompleted.addListener(details=>{
  if(details.statusCode===403){
    if(globalThis.PH_TARGET_SAFETY)globalThis.PH_TARGET_SAFETY.http403(details.url).catch(()=>{});
    else stopForSecurity('HTTP 403: '+details.url,true).catch(()=>{});
  }
},{urls:['https://www.tiktok.com/*'],types:['main_frame','xmlhttprequest']});
