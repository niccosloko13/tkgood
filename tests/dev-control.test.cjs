const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const build='1'.repeat(16), id='a'.repeat(32);

function worker(storage,command,events,options={}) {
  let currentUrl=options.initialUrl||'https://www.tiktok.com/@maker/video/123';
  let loading=!!options.loadingOnce;
  const context=vm.createContext({URL,AbortSignal,Date,PH_DEV:{extension_id:id,token:'local-token'},PH_BUILD_ID:options.build||build,
    fetch:async (url,opts)=>{
      events.push({url,body:opts.body?JSON.parse(opts.body):null});
      assert.equal(opts.headers['X-PH-Dev-Token'],'local-token');
      return {ok:true,json:async()=>url.endsWith('/next')?{command}: {ok:true}};
    },
    chrome:{runtime:{id,reload(){events.push({reload:true});}},storage:{local:{
      get:async key=>({[key]:storage[key]}),set:async value=>Object.assign(storage,JSON.parse(JSON.stringify(value))),remove:async key=>{delete storage[key];}
    }},scripting:{executeScript:async options=>{events.push({probe:options});return [{frameId:0,result:{mode:'READ_ONLY_SESSION_PROBE',url:currentUrl,document_ready:'complete'}}];}},tabs:{
      query:async()=>options.noTabs?[]:[{id:1,url:currentUrl},{id:2,url:'https://example.com/'},{id:3,url:'https://www.tiktok.com.evil.test/'}],
      create:async changes=>{events.push({create:changes.url});currentUrl=changes.url;return {id:1};},
      get:async tabId=>{if(loading){loading=false;return {id:tabId,url:'',pendingUrl:currentUrl,status:'loading'};}return {id:tabId,url:tabId===1?currentUrl:'https://example.com/',status:'complete'};},
      update:async(tabId,changes)=>{events.push({navigate:tabId,url:changes.url});currentUrl=changes.url;},
      reload:async tabId=>events.push({refresh:tabId}),
      sendMessage:async()=>({page_ready_state:'complete',build_id:options.contentBuild||build,...options.signals})
    }}});
  vm.runInContext(fs.readFileSync('extension/dev_worker.js','utf8'),context);
  return ()=>vm.runInContext('ProductHunterDev.tick()',context);
}

function command(type='DEV_RELOAD_EXTENSION') {
  return {id:'f'.repeat(32),type,expected_build:build,extension_id:id,created_at:new Date().toISOString()};
}

test('self reload persists flag, acknowledges before runtime reload, recovers in a new worker and refreshes only TikTok',async()=>{
  const storage={},events=[],job=command();
  await worker(storage,job,events)();
  assert.equal(storage.pendingDevReload.phase,'accepted');
  assert.ok(events.findIndex(e=>e.url?.endsWith('/accept'))<events.findIndex(e=>e.reload));
  assert.equal(events.filter(e=>e.refresh).length,0);
  await worker(storage,null,events)();
  assert.deepEqual(events.filter(e=>e.refresh).map(e=>e.refresh),[1]);
  assert.equal(events.at(-1).body.status,'SUCCEEDED');
  assert.equal(events.at(-1).body.build_id,build);
  assert.equal(storage.pendingDevReload,undefined);
});

test('renew opens a single home in the existing browser, retains latch and never creates another tab',async()=>{
 const storage={securityStop:incident},events=[],job={...command('DEV_RENEW_TIKTOK_SESSION'),options_json:JSON.stringify({incident})};
 const tick=worker(storage,job,events,{noTabs:true,signals:{current_page_status:'healthy',tiktok_session_status:'unconfirmed'}});
 await tick();assert.equal(events.filter(e=>e.create).length,1);
 assert.deepEqual(events.find(e=>e.create),{create:'https://www.tiktok.com/'});
 assert.equal(events.at(-1).body.status,'SUCCEEDED');assert.deepEqual(storage.securityStop,incident);
 assert.equal(events.filter(e=>e.refresh||e.navigate).length,0);
});

test('DOM probe reads the pinned existing tab with fixed packaged code and no navigation',async()=>{
 const storage={securityStop:incident},events=[];
 const job={...command('DEV_INSPECT_TIKTOK_SESSION'),options_json:JSON.stringify({tab_id:1,current_url:'https://www.tiktok.com/'})};
 await worker(storage,job,events,{initialUrl:'https://www.tiktok.com/'})();
 assert.equal(events.filter(e=>e.probe).length,1);
 assert.deepEqual(Array.from(events.find(e=>e.probe).probe.files),['session_probe.js']);
 assert.equal(events.filter(e=>e.create||e.navigate||e.refresh||e.reload).length,0);
 assert.equal(events.at(-1).body.status,'SUCCEEDED');
 assert.deepEqual(storage.securityStop,incident);
});

test('renew waits for a newly created loading tab with an empty URL without retrying creation',async()=>{
 const storage={},events=[],tick=worker(storage,command('DEV_RENEW_TIKTOK_SESSION'),events,{noTabs:true,loadingOnce:true,signals:{current_page_status:'healthy'}});
 await tick();assert.equal(storage.pendingDevReload.phase,'renew_attempted');
 await tick();assert.equal(events.filter(e=>e.create).length,1);assert.equal(events.at(-1).body.status,'SUCCEEDED');
});

test('renew stops if a new HTTP incident arrives while waiting for the home',async()=>{
 const storage={},events=[],tick=worker(storage,command('DEV_RENEW_TIKTOK_SESSION'),events,{noTabs:true,loadingOnce:true});
 await tick();storage.securityStop={reason:'HTTP 403: https://www.tiktok.com/',observed_at:new Date().toISOString()};
 await tick();await tick();assert.equal(events.filter(e=>e.create).length,1);assert.equal(events.at(-1).body.status,'FAILED');
 assert.match(events.at(-1).body.detail,/New security incident/);
});

test('renew with an existing healthy current-build home does not navigate or reload',async()=>{
 const storage={},events=[];
 await worker(storage,command('DEV_RENEW_TIKTOK_SESSION'),events,{initialUrl:'https://www.tiktok.com/',signals:{current_page_status:'healthy'}})();
 assert.equal(events.filter(e=>e.create||e.navigate||e.refresh).length,0);
 assert.equal(events.at(-1).body.status,'SUCCEEDED');
});

test('renew does not navigate away from a currently blocked page',async()=>{
 const storage={securityStop:incident},events=[];
 const tick=worker(storage,{...command('DEV_RENEW_TIKTOK_SESSION'),options_json:JSON.stringify({incident})},events,{signals:{current_page_status:'http_403'}});
 await tick();await tick();
 assert.equal(events.filter(e=>e.create||e.navigate||e.refresh).length,0);
 assert.equal(events.at(-1).body.status,'FAILED');assert.deepEqual(storage.securityStop,incident);
});

test('backend negotiation disables command polling instead of a continuous 404 loop',async()=>{
 let requests=0;
 const ctx=vm.createContext({URL,AbortSignal,Date,PH_API_VERSION:'1',PH_DEV:{extension_id:id,token:'local'},PH_BUILD_ID:build,
  fetch:async()=>{requests++;return {ok:false,status:404};},chrome:{runtime:{id},storage:{local:{get:async()=>({}),set:async()=>{},remove:async()=>{}}}}});
 vm.runInContext(fs.readFileSync('extension/dev_worker.js','utf8'),ctx);
 await vm.runInContext("ProductHunterDev.setBackendContract({api_version:'1',dev_control_enabled:false});ProductHunterDev.tick()",ctx);
 assert.equal(requests,0);
 await vm.runInContext("ProductHunterDev.setBackendContract({api_version:'1',dev_control_enabled:true,backend_run_id:'a'});ProductHunterDev.tick()",ctx);
 for(let i=0;i<3;i++)await vm.runInContext('ProductHunterDev.tick()',ctx);
 assert.equal(requests,1);
});

const incident={reason:'HTTP 403: https://www.tiktok.com/@maker/video/123',observed_at:'2026-10-22T12:00:00Z'};
test('reload under a latch updates only worker; never refreshes known failed video',async()=>{
 const storage={securityStop:incident},events=[];
 await worker(storage,command(),events)();
 await worker(storage,null,events)();
 assert.equal(events.filter(e=>e.refresh||e.navigate).length,0);
 assert.equal(events.at(-1).body.status,'SUCCEEDED');
 assert.deepEqual(storage.securityStop,incident);
});
test('explicit home validation reuses tab and navigates once without clearing latch or searching',async()=>{
 const storage={securityStop:incident},events=[];
 const job={...command('DEV_VALIDATE_TIKTOK_HOME'),options_json:JSON.stringify({incident})};
 const tick=worker(storage,job,events,{signals:{current_page_status:'healthy',tiktok_session_status:'confirmed',
  session_evidence:['visible_own_profile_with_avatar','visible_account_inbox']}});
 await tick();assert.equal(storage.pendingDevReload.phase,'refreshed');
 await tick();
 assert.deepEqual(events.filter(e=>e.navigate),[{navigate:1,url:'https://www.tiktok.com/'}]);
 assert.equal(events.filter(e=>e.refresh).length,0);
 assert.equal(events.at(-1).body.status,'SUCCEEDED');
 assert.deepEqual(storage.securityStop,incident);
});
test('home challenge fails once and does not retry navigation',async()=>{
 const storage={securityStop:incident},events=[];
 const job={...command('DEV_VALIDATE_TIKTOK_HOME'),options_json:JSON.stringify({incident})};
 const tick=worker(storage,job,events,{signals:{current_page_status:'challenge'}});
 await tick();await tick();
 assert.equal(events.filter(e=>e.navigate).length,1);
 assert.equal(events.at(-1).body.status,'FAILED');
 assert.deepEqual(storage.securityStop,incident);
});
test('new incident refuses previously queued home recovery before any navigation',async()=>{
 const storage={securityStop:{...incident,observed_at:'2026-10-23T12:00:00Z'}},events=[];
 const tick=worker(storage,{...command('DEV_VALIDATE_TIKTOK_HOME'),options_json:JSON.stringify({incident})},events);
 await tick();await tick();
 assert.equal(events.filter(e=>e.navigate||e.refresh).length,0);
 assert.equal(events.at(-1).body.status,'FAILED');
});
test('known failed URL stays excluded from default refresh after latch clearance',async()=>{
 const storage={failedVideoUrls:[incident.reason.slice('HTTP 403: '.length)]},events=[];
 await worker(storage,command('DEV_REFRESH_TIKTOK'),events)();
 assert.equal(events.filter(e=>e.navigate||e.refresh).length,0);
 assert.equal(events.at(-1).body.refreshed_tabs,0);
});

test('refresh command reloads TikTok without reloading the extension',async()=>{
  const storage={},events=[];
  await worker(storage,command('DEV_REFRESH_TIKTOK'),events)();
  assert.equal(events.some(e=>e.reload),false);
  assert.deepEqual(events.filter(e=>e.refresh).map(e=>e.refresh),[1]);
  assert.equal(events.at(-1).body.refreshed_tabs,1);
});

test('reconnection waits for the new content build and does not repeat tab reload',async()=>{
  const storage={},events=[];
  await worker(storage,command('DEV_REFRESH_TIKTOK'),events,{contentBuild:'2'.repeat(16)})();
  assert.equal(storage.pendingDevReload.phase,'refreshed');
  assert.equal(events.some(e=>e.url?.endsWith('/complete')),false);
  await worker(storage,null,events)();
  assert.equal(events.filter(e=>e.refresh).length,1);
  assert.equal(storage.pendingDevReload,undefined);
});

test('refresh timeout reports failure and clears flag only after acknowledged completion',async()=>{
  const storage={pendingDevReload:{...command(),created_at:'2000-01-01T00:00:00Z',phase:'refreshed',tabs:[1]}},events=[];
  await worker(storage,null,events)();
  assert.equal(events.at(-1).body.status,'FAILED');
  assert.match(events.at(-1).body.detail,/Timed out/);
  assert.equal(storage.pendingDevReload,undefined);
});

test('worker outside the provisioned extension cannot issue maintenance calls',async()=>{
  const context=vm.createContext({PH_DEV:{extension_id:'other'},chrome:{runtime:{id}},URL});
  vm.runInContext(fs.readFileSync('extension/dev_worker.js','utf8'),context);
  assert.equal(await vm.runInContext('ProductHunterDev.tick()',context),false);
});

test('initial local bootstrap requires backend development authorization and reloads once per build',async()=>{
  const storage={},status={},events=[];
  let authorized=false;
  const context=vm.createContext({AbortSignal,PH_DEV:{extension_id:id,token:'local-token'},PH_BUILD_ID:build,
    document:{getElementById:()=>status},fetch:async()=>({ok:authorized}),
    chrome:{runtime:{id,reload:()=>events.push('reload')},storage:{local:{
      get:async key=>({[key]:storage[key]}),set:async data=>Object.assign(storage,data)
    }}}});
  const code=fs.readFileSync('extension/dev_bootstrap.js','utf8');
  vm.runInContext(code,context);
  for(let i=0;i<5;i++) await new Promise(resolve=>setImmediate(resolve));
  assert.equal(events.length,0);
  authorized=true;
  vm.runInContext(code,context);
  for(let i=0;i<5;i++) await new Promise(resolve=>setImmediate(resolve));
  assert.equal(events.length,1);
  assert.equal(storage.devBootstrapBuild,build);
  vm.runInContext(code,context);
  for(let i=0;i<5;i++) await new Promise(resolve=>setImmediate(resolve));
  assert.equal(events.length,1);
});
