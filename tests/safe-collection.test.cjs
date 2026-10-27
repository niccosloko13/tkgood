const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {domFixture}=require('./dom-fixture.cjs');
const {extractSearchResults}=require('../extension/search_results.js');
test('bounded extraction reads no more than ten visible cards without scroll or engagement',()=>{
 const html=Array.from({length:25},(_,i)=>`<article><a href="/@maker/video/${100+i}">Product ${i}</a></article>`).join('');
 const {document,window}=domFixture(html);
 document.querySelectorAll('a').forEach(a=>a.click=()=>assert.fail('no clicks'));
 window.scrollBy=()=>assert.fail('no scrolling');
 const results=extractSearchResults(document,window,10);
 assert.equal(results.length,10);assert.equal(results.linksDetected,10);
});

function worker({page='healthy',error=null,count=10,tabs=null,signalSamples=null,strictHealth=false}={}){
 const code=fs.readFileSync('extension/background.js','utf8');const start=code.indexOf('async function readBoundedSearch('),end=code.indexOf('async function readVideoDetail(',start);
 const messages=[],stops=[],routes=[];let heartbeats=0,tabIndex=0,signalIndex=0;
 const ctx=vm.createContext({Date,Error,URL,ProductHunterSafetyGate:require('../extension/safety_gate.js'),ProductHunterDiscovery:require('../extension/search_discovery.js'),ProductHunterPacing:{sleep:async()=>{}},pacing:{pollMs:1000,searchTimeoutMs:25000,stableSamples:2,stabilityAttempts:8},
  assertSafe:async()=>{},stopForSecurity:async reason=>stops.push(reason),request:async()=>{heartbeats++;return {};},
  chrome:{storage:{local:{set:async value=>{if(value.safeSearchRouteDiagnostic)routes.push(value.safeSearchRouteDiagnostic);}}},runtime:{id:'ext'},tabs:{get:async()=>tabs?tabs[Math.min(tabIndex++,tabs.length-1)]:({status:'complete',url:'https://www.tiktok.com/search?q=home'}),sendMessage:async(id,m)=>{messages.push(m);return m.type==='PH_SIGNALS'?{page_ready_state:'complete',current_page_status:page,tiktok_session_status:'confirmed',...(signalSamples?signalSamples[Math.min(signalIndex++,signalSamples.length-1)]:{})}:error?{ok:false,error}:{ok:true,capture:{page_url:'https://www.tiktok.com/search?q=home',results_count:count,links_detected:count,results:Array(count).fill({})}};}}}});
 vm.runInContext(code.slice(start,end),ctx);
 return {run:()=>vm.runInContext(`readBoundedSearch(7,'home',10,'https://www.tiktok.com/',null,${strictHealth})`,ctx),messages,stops,routes,heartbeats:()=>heartbeats};
}

test('search URL semantic policy accepts benign canonical differences only',()=>{
 const {searchPage,routeDiagnostic}=require('../extension/search_discovery.js');
 for(const path of ['/search?q=home%20gadgets','/search?q=home+gadgets','/search?lang=pt-BR&q=home%20gadgets','/search?q=home%20gadgets&source=search','/search/?q=home%20gadgets','/search?q=%20HOME%20%20gadgets%20'])assert.ok(searchPage('https://www.tiktok.com'+path,'home gadgets'),path);
 assert.ok(searchPage('https://tiktok.com/search?q=home+gadgets','home gadgets'));
 assert.ok(searchPage('https://WWW.TIKTOK.COM:443/search?q=caf%C3%A9','cafe\u0301'));
 for(const url of ['https://www.tiktok.com/@foo/video/123','https://www.tiktok.com/video/123','https://www.tiktok.com/login','https://www.tiktok.com/challenge','https://www.tiktok.com/captcha','https://www.tiktok.com/verify','https://example.com/search?q=home+gadgets','https://www.tiktok.com/search?q=other+query','https://www.tiktok.com/search?q=home+gadgets&q=other','http://www.tiktok.com/search?q=home+gadgets','https://www.tiktok.com:444/search?q=home+gadgets','https://www.tiktok.com/search/unexpected?q=home+gadgets'])assert.equal(searchPage(url,'home gadgets'),false,url);
 const diagnostic=routeDiagnostic('https://www.tiktok.com/search?q=home+gadgets','https://user:secret@www.tiktok.com/search?q=home+gadgets&token=secret#secret','home gadgets');
 assert.ok(!JSON.stringify(diagnostic).includes('secret'));assert.equal(diagnostic.actual_query,'home gadgets');
});

test('pending search navigation waits for commit without an extra card read',async()=>{
 const w=worker({tabs:[{status:'loading',url:'https://www.tiktok.com/',pendingUrl:'https://www.tiktok.com/search?q=home'},{status:'complete',url:'https://www.tiktok.com/search/?source=search&q=home'}]});
 await w.run();assert.equal(w.messages.filter(m=>m.type==='PH_READ_SEARCH_RESULTS').length,1);
 assert.equal(w.routes[0].actual_path,'/');assert.equal(w.routes[1].actual_path,'/search/');
});

test('completed unexpected routes fail before any card read; challenge latches',async()=>{
 for(const path of ['/login','/@foo/video/123','/challenge']){
  const w=worker({tabs:[{status:'complete',url:'https://www.tiktok.com'+path}]});
  await assert.rejects(w.run(),/Safe search route changed/);assert.equal(w.messages.length,0);assert.equal(w.stops.length,path==='/challenge'?1:0);
 }
});
test('one bounded viewport read stops after capture',async()=>{
 const w=worker();assert.equal((await w.run()).results_count,10);
 assert.equal(w.messages.filter(m=>m.type==='PH_READ_SEARCH_RESULTS').length,1);
 assert.equal(w.heartbeats(),1);assert.equal(w.stops.length,0);
 assert.ok(w.messages.every(m=>['PH_SIGNALS','PH_READ_SEARCH_RESULTS'].includes(m.type)));
});
test('challenge and 403 stop without retry or recapture',async()=>{
 for(const opts of [{page:'challenge'},{error:'HTTP 403 Access Denied'},{error:'CAPTCHA verify human'}]){
  const w=worker(opts);await assert.rejects(w.run(),/Security block/);
  assert.equal(w.stops.length,1);assert.ok(w.messages.filter(m=>m.type==='PH_READ_SEARCH_RESULTS').length<=1);
  assert.equal(w.heartbeats(),0);
 }
});
test('unknown readiness has a hard sample limit; empty capture is never read twice',async()=>{
 for(const opts of [{page:'unknown'},{count:0}]){
  const w=worker(opts);await assert.rejects(w.run());assert.ok(w.messages.length<=8);assert.equal(w.heartbeats(),0);
  assert.equal(w.messages.filter(m=>m.type==='PH_READ_SEARCH_RESULTS').length,opts.count===0?1:0);
 }
});

test('transient unknown readiness waits passively for two healthy samples before one card read',async()=>{
 const w=worker({signalSamples:[{current_page_status:'unknown',tiktok_session_status:'unconfirmed'},{},{},{}]});
 await w.run();assert.equal(w.messages.filter(m=>m.type==='PH_SIGNALS').length,3);
 assert.equal(w.messages.filter(m=>m.type==='PH_READ_SEARCH_RESULTS').length,1);assert.equal(w.stops.length,0);
});

test('challenge or degraded login during readiness stops before any card read',async()=>{
 for(const sample of [{current_page_status:'challenge'},{tiktok_session_status:'login_required'}]){
  const w=worker({signalSamples:[{},sample]});await assert.rejects(w.run(),/Security block/);
  assert.equal(w.messages.filter(m=>m.type==='PH_READ_SEARCH_RESULTS').length,0);assert.equal(w.stops.length,1);
 }
});

test('Stage 2 unconfirmed or unhealthy search stops on the first sample without reading cards',async()=>{
 for(const sample of [{current_page_status:'unknown'},{tiktok_session_status:'unconfirmed'}]){
  const w=worker({strictHealth:true,signalSamples:[sample,{},{}]});await assert.rejects(w.run(),/Stage 2 session\/page not healthy/);
  assert.equal(w.messages.length,1);assert.equal(w.messages[0].type,'PH_SIGNALS');assert.equal(w.heartbeats(),0);
 }
});

test('bounded extraction reports visible invalid video links without counting hidden links',()=>{
 const {document,window}=domFixture('<article><a href="https://example.com/@bad/video/123">invalid</a></article><article><a href="/@maker/video/124">valid</a></article>');
 const results=extractSearchResults(document,window,10);
 assert.equal(results.invalidDetected,1);assert.equal(results.length,1);assert.equal(results.linksDetected,1);
});
