const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
test('security checks use DOM evidence and work in hidden documents without mutation',()=>{
 const context=vm.createContext({});vm.runInContext(fs.readFileSync('extension/safety.js','utf8'),context);
 for(const text of ['Access Denied','HTTP 403','Verify you are human','Complete the captcha']){
  const doc={visibilityState:'hidden',body:{textContent:text},querySelector:()=>null};
  assert.throws(()=>context.ProductHunterSafety.assertSafe(doc),/Security stop/);
  assert.equal(doc.visibilityState,'hidden');
 }
 assert.equal(context.ProductHunterSafety.reason({title:'TikTok',body:{innerText:'portable blender'},querySelector:()=>null}),null);
});
test('pacing is centralized with bounded retries and nonzero cooldown',()=>{
 const context=vm.createContext({});vm.runInContext(fs.readFileSync('extension/pacing.js','utf8'),context);
 const p=context.ProductHunterPacing.settings;
 assert.ok(p.cooldownMs>=2000);assert.ok(p.pollMs>=1000);assert.equal(p.stableSamples,2);assert.equal(p.transportAttempts,3);
});

test('normal restoration is bounded to a minimized window, without visibility spoofing or focus retries',async()=>{
 let state='minimized';const updates=[];
 const event=()=>({addListener(){}});
 const context=vm.createContext({URL,AbortSignal,setInterval(){},setTimeout,Date,
  fetch:async()=>({ok:true,json:async()=>({command:null})}),
  chrome:{runtime:{id:'ext',getManifest:()=>({version:'test'}),onMessage:event(),onInstalled:event(),onStartup:event()},
   alarms:{create:async()=>{},onAlarm:event()},storage:{local:{get:async()=>({}),set:async()=>{}}},
   windows:{get:async()=>({state}),update:async(id,value)=>{updates.push({id,...value});state=value.state;}},
   tabs:{query:async()=>[],onRemoved:event(),onUpdated:event(),update:async()=>assert.fail('already active tab is reused')}}});
 vm.runInContext(fs.readFileSync('extension/pacing.js','utf8')+fs.readFileSync('extension/background.js','utf8'),context);
 for(let i=0;i<2;i++)await vm.runInContext('prepareExistingTab({id:7,windowId:9,active:true})',context);
 assert.deepEqual(updates,[{id:9,state:'normal'}]);
});

test('latched security stop publishes diagnostics but performs no collector reads or command claims',async()=>{
 const calls=[],reads=[],devTicks=[];const stored={securityStop:{reason:'HTTP 403'}};
 const event=()=>({addListener(){}});
 const context=vm.createContext({URL,AbortSignal,Date,setInterval(){},setTimeout,ProductHunterDev:{tick:async()=>{devTicks.push(true);return false;}},
  fetch:async(url,options)=>{calls.push({url,body:options.body&&JSON.parse(options.body)});return {ok:true,json:async()=>({})};},
  chrome:{runtime:{id:'ext',getManifest:()=>({version:'test'}),onMessage:event(),onInstalled:event(),onStartup:event()},
   alarms:{create:async()=>{},onAlarm:event()},storage:{local:{get:async key=>({[key]:stored[key]}),set:async value=>Object.assign(stored,value)}},
   tabs:{query:async()=>[{id:7,url:'https://www.tiktok.com/search?q=home+gadgets'}],
    sendMessage:async(id,message)=>reads.push(message),onRemoved:event(),onUpdated:event()}}});
 vm.runInContext(fs.readFileSync('extension/pacing.js','utf8')+fs.readFileSync('extension/background.js','utf8'),context);
 for(let i=0;i<10;i++)await new Promise(resolve=>setImmediate(resolve));
 await vm.runInContext('tick()',context);
 assert.ok(reads.length>0);assert.ok(reads.every(m=>m.type==='PH_SIGNALS'));assert.ok(calls.every(c=>c.url.endsWith('/api/bridge/heartbeat')));
 assert.ok(calls.every(c=>c.body.security_stop==='HTTP 403'));
 assert.ok(devTicks.length>0);
});

test('fixed live session-reader installation under latch never navigates or unlocks collection',async()=>{
 const calls=[],reads=[],injections=[],stored={securityStop:{reason:'HTTP 403 historical'}};let installed=false;
 const event=()=>({addListener(){}});
 const context=vm.createContext({URL,AbortSignal,Date,setInterval(){},setTimeout,ProductHunterDev:{tick:async()=>false},
  fetch:async(url,opts)=>{calls.push({url,body:opts.body&&JSON.parse(opts.body)});return {ok:true,json:async()=>({})};},
  chrome:{runtime:{id:'ext',getManifest:()=>({version:'test'}),onMessage:event(),onInstalled:event(),onStartup:event()},
   alarms:{create:async()=>{},onAlarm:event()},storage:{local:{get:async key=>({[key]:stored[key]}),set:async v=>Object.assign(stored,v)}},
   scripting:{executeScript:async opts=>{injections.push(opts);installed=true;}},
   tabs:{query:async()=>[{id:7,url:'https://www.tiktok.com/'}],onRemoved:event(),onUpdated:event(),
    create:()=>assert.fail('no new tab'),update:()=>assert.fail('no navigation'),reload:()=>assert.fail('no reload'),
    sendMessage:async(id,m)=>{reads.push(m.type);if(!installed)throw Error('No receiver');return {current_page_status:'healthy',tiktok_session_status:'confirmed',page_ready_state:'complete',session_signals:{profile_route_present:true,messages_route_present:true},session_evidence:['visible_account_inbox']};}}}});
 vm.runInContext(fs.readFileSync('extension/pacing.js','utf8')+fs.readFileSync('extension/background.js','utf8'),context);
 for(let i=0;i<15;i++)await new Promise(r=>setImmediate(r));
 assert.equal(injections.length,1);assert.deepEqual(Array.from(injections[0].files),['session_signals.js','session_observer.js']);
 assert.ok(reads.every(t=>t==='PH_SESSION_SIGNALS'));
 assert.ok(calls.every(c=>c.url.endsWith('/api/bridge/heartbeat')));
 assert.equal(calls[0].body.tiktok_session_status,'confirmed');assert.equal(calls[0].body.security_stop,'HTTP 403 historical');
 assert.equal(stored.securityStop.reason,'HTTP 403 historical');
});
