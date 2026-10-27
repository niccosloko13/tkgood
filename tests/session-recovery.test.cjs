const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');

function session(html) {
 const {document}=parseHTML(html);document.readyState='complete';
 document.defaultView.getComputedStyle=()=>({display:'block',visibility:'visible'});
 for(const n of document.querySelectorAll('*'))n.getBoundingClientRect=()=>({width:20,height:20});
 const context=vm.createContext({URL});
 vm.runInContext(fs.readFileSync('extension/safety.js','utf8')+fs.readFileSync('extension/session_signals.js','utf8'),context);
 return context.ProductHunterSession.read(document,'https://www.tiktok.com/');
}
test('generic Following/Profile/Messages text never confirms authentication',()=>{
 const s=session('<html><body><main>Following Profile Messages</main></body></html>');
 assert.equal(s.current_page_status,'healthy');assert.equal(s.tiktok_session_status,'unconfirmed');
});
test('visible own navigation profile avatar and account inbox confirm a ready healthy page',()=>{
 const s=session('<html><body><main><a data-e2e="nav-profile" href="/@myaccount"><img></a><a href="/messages">Inbox</a></main></body></html>');
 assert.equal(s.tiktok_session_status,'confirmed');assert.equal(s.session_evidence.length,2);
});
test('a creator card, a hidden profile or visible login cannot confirm the session',()=>{
 for(const profile of ['<a href="/@creator"><img></a>','<a hidden data-e2e="nav-profile" href="/@myaccount"><img></a>',
  '<button data-e2e="top-login-button">Login</button><a data-e2e="nav-profile" href="/@myaccount"><img></a>']) {
  assert.notEqual(session('<html><body><main>'+profile+'<a href="/messages">Inbox</a></main></body></html>').tiktok_session_status,'confirmed');
 }
});
test('403 and challenges dominate account controls',()=>{
 for(const text of ['HTTP 403','Access Denied','Complete the captcha']) {
  const s=session('<html><body><main>'+text+' <a data-e2e="nav-profile" href="/@me"><img></a><a href="/messages">Inbox</a></main></body></html>');
  assert.notEqual(s.current_page_status,'healthy');assert.notEqual(s.tiktok_session_status,'confirmed');
 }
});

test('current structural nav buttons confirm independently from localized text and old hidden inbox',()=>{
 const s=session('<html><body><div><a data-e2e="nav-following" href="/following">x</a><a data-e2e="nav-profile" href="/@own"><img></a><button data-e2e="nav-messages" role="listitem" aria-label="Mensagens">x</button><button data-e2e="nav-activity" role="listitem" aria-label="Atividade">x</button><div hidden data-e2e="inbox-icon"></div><ul><li><a data-e2e="following-user-button" href="/@followed"><img></a></li></ul></div><main></main></body></html>');
 assert.equal(s.tiktok_session_status,'confirmed');
 for(const key of ['profile_route_present','messages_route_present','activity_or_inbox_present','authenticated_sidebar_present','account_avatar_present','following_authenticated_present'])assert.equal(s.session_signals[key],true);
 assert.equal(s.session_signals.logged_out_cta_present,false);
 assert.equal(s.session_debug.messages_route_present.sample_data_e2e,'nav-messages');
 assert.equal(s.session_debug.activity_or_inbox_present.matched_count,2);
 assert.equal(s.session_debug.activity_or_inbox_present.visible_count,1);
});

test('partial positive evidence is retained and correlated controls do not count twice',()=>{
 for(const html of ['<a data-e2e="nav-profile" href="/@own"><img></a>','<button data-e2e="nav-messages"></button><button data-e2e="nav-activity"></button>']){
  const s=session('<main>'+html+'</main>');assert.equal(s.tiktok_session_status,'unconfirmed');assert.equal(s.session_evidence.length,1);
 }
 assert.equal(session('<main><a data-e2e="nav-following" href="/following">Following</a></main>').session_signals.following_authenticated_present,false);
});

test('persisted collection latch cannot invalidate healthy current account DOM',()=>{
 const {document}=parseHTML('<main><a data-e2e="nav-profile" href="/@own"><img></a><button data-e2e="nav-messages"></button></main>');document.readyState='complete';
 document.defaultView.getComputedStyle=()=>({display:'block',visibility:'visible'});
 for(const n of document.querySelectorAll('*'))n.getBoundingClientRect=()=>({width:20,height:20});
 const context=vm.createContext({URL});vm.runInContext(fs.readFileSync('extension/safety.js','utf8')+fs.readFileSync('extension/session_signals.js','utf8'),context);
 context.ProductHunterSafety.stop('HTTP 403 historical video');
 assert.equal(context.ProductHunterSession.read(document,'https://www.tiktok.com/').tiktok_session_status,'confirmed');
 assert.throws(()=>context.ProductHunterSafety.assertSafe(document),/Security stop/);
});
