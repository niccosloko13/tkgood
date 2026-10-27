const {test}=require('node:test'),assert=require('node:assert/strict');
const {wait}=require('../extension/search_stability.js');
require('../extension/safety_gate.js');
const {settings}=(()=>{require('../extension/pacing.js');return globalThis.ProductHunterPacing;})();
const URL='https://www.tiktok.com/search?q=home+finds';
function harness(samples,{phase='POST_NAVIGATION',tabs=null}={}){
 let time=0,index=0,tabIndex=0;const calls=[],stops=[];
 const diagnostics={query:'home finds',pre_health:{samples:[]},settle_samples:[],final_health:null};
 const env={pacing:settings,now:()=>time,sleep:async ms=>{time+=ms;},assertSafe:async()=>{},stopForSecurity:async reason=>stops.push(reason),chrome:{tabs:{get:async()=>tabs?tabs[Math.min(tabIndex++,tabs.length-1)]:{url:URL,status:'complete'},sendMessage:async(id,m)=>{calls.push(m);const s=samples[Math.min(index++,samples.length-1)];if(s instanceof Error)throw s;return {page_ready_state:'complete',current_page_status:'healthy',tiktok_session_status:'confirmed',current_url:URL,...s};}}}};
 return {run:()=>wait({tabId:1,phase,expectedUrl:URL,deadlineMs:25000,diagnostics},env),diagnostics,calls,stops,time:()=>time};
}
test('pre-query requires two consecutive real samples separated by normal pacing',async()=>{
 const h=harness([{current_page_status:'unknown'},{},{}],{phase:'PRE_QUERY'});await h.run();
 assert.equal(h.diagnostics.pre_health.samples.length,3);assert.equal(h.time(),2000);assert.equal(h.diagnostics.pre_health.final_health.consecutive,2);
 assert.ok(h.calls.every(m=>m.type==='PH_SIGNALS'));
});
test('post-navigation settles then tolerates unknown/incomplete before healthy pair',async()=>{
 const h=harness([new Error('old document removed'),{page_ready_state:'loading'},{current_page_status:'unknown',tiktok_session_status:'unconfirmed'},{},{}]);await h.run();
 assert.equal(h.diagnostics.settle_samples.length,5);assert.equal(h.diagnostics.final_health.consecutive,2);assert.equal(h.stops.length,0);
});
test('a healthy old document or loading tab cannot satisfy the post-nav gate',async()=>{
 const h=harness([{current_url:'https://www.tiktok.com/search?q=home+gadgets'},{},{},{}],{tabs:[{url:URL,status:'loading'},{url:URL,status:'loading'},{url:URL,status:'complete'}]});await h.run();
 assert.equal(h.diagnostics.final_health.elapsed_ms,3000);assert.equal(h.diagnostics.settle_samples[0].consecutive,0);
});
test('persistent transient state ends with SESSION_NOT_STABLE within 25 seconds',async()=>{
 const h=harness([{current_page_status:'unknown',tiktok_session_status:'unconfirmed'}]);await assert.rejects(h.run(),/SESSION_NOT_STABLE/);
 assert.equal(h.time(),25000);assert.equal(h.stops.length,0);assert.equal(h.calls.length,25);
});
test('403, challenge, captcha and confirmed logout stop on first sample, without waiting',async()=>{
 for(const sample of [{current_page_status:'http_403'},{security_stop:'HTTP 403'},{current_page_status:'challenge'},{security_stop:'captcha'},{security_stop:'verify human'},{tiktok_session_status:'login_required'},{session_signals:{logged_out_cta_present:true}}]){
  const h=harness([sample]);await assert.rejects(h.run());assert.equal(h.time(),0);assert.equal(h.stops.length,1);assert.equal(h.calls.length,1);
 }
});
test('external host fails immediately and wrong search query fails after short route grace',async()=>{
 const external=harness([{}],{tabs:[{url:'https://example.com/',status:'complete'}]});await assert.rejects(external.run(),/UNEXPECTED_HOST/);assert.equal(external.calls.length,0);
 const wrong=harness([{}],{tabs:[{url:'https://www.tiktok.com/search?q=other',status:'complete'}]});await assert.rejects(wrong.run(),/SEARCH_ROUTE_INVALID_PERSISTENT/);assert.equal(wrong.time(),3000);
});

test('known pending search transition can load past route grace without authorizing old document',async()=>{
 const pending={url:'https://www.tiktok.com/search?q=home+gadgets',pendingUrl:URL,status:'loading'};
 const h=harness([{}],{tabs:[pending,pending,pending,pending,pending,{url:URL,status:'complete'}]});await h.run();
 assert.equal(h.diagnostics.final_health.elapsed_ms,6000);assert.equal(h.stops.length,0);
});
