const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {parseHTML}=require('linkedom');
function setup(){
 const html=fs.readFileSync('app/static/index.html','utf8'),{document,window}=parseHTML(html);
 const timers=new Map();let id=0;
 const context=vm.createContext({document,window,URL,console,Date,
  setTimeout:(fn,ms)=>{const key=++id;timers.set(key,{fn,ms});return key;},clearTimeout:key=>timers.delete(key),
  setInterval:()=>assert.fail('no interval polling'),
  localStorage:{getItem:()=>null,setItem:()=>{}},fetch:()=>new Promise(()=>{}),alert:()=>assert.fail('connection errors must be inline')});
 vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
 return {document,window,context,timers,panel:context.BabiConnectionPanel};
}
function bridge(changes={}){return {companion_connected:true,extension_connected:true,companion_compatible:true,heartbeat_fresh:true,
 chrome_connected:true,tiktok_open:true,current_url:'https://www.tiktok.com/',page_ready_state:'complete',current_page_status:'healthy',
 tiktok_session_status:'unconfirmed',security_stop_active:true,session_evidence:[],last_seen:'2026-10-24T00:00:00Z',...changes};}
const settle=()=>new Promise(r=>setImmediate(r));

test('one timer survives repeated starts, section changes and pagehide cancels it',()=>{
 const x=setup();assert.equal(x.timers.size,1);
 x.context.BabiPolling.start();x.context.BabiPolling.start();assert.equal(x.timers.size,1);
 vm.runInContext("showSection('connection');showSection('overview');showSection('connection')",x.context);
 assert.equal(x.timers.size,1);assert.equal([...x.timers.values()][0].ms,3000);
 x.window.dispatchEvent(new x.window.Event('pagehide'));assert.equal(x.timers.size,0);
});
test('unchanged state causes no DOM mutations or container replacement and buttons retain identity',async()=>{
 const x=setup(),b=bridge();x.panel.render(b);
 const buttons=['openTikTokButton','renewSession','verifySession','refreshConnectionButton'].map(id=>x.document.getElementById(id));
 const facts=x.document.getElementById('connectionFacts'),node=facts.firstElementChild;
 Object.defineProperty(facts,'innerHTML',{set:()=>assert.fail('no full innerHTML replacement')});
 let mutations=0;const observer=new x.window.MutationObserver(rows=>mutations+=rows.length);
 observer.observe(x.document.querySelector('[data-section="connection"]'),{subtree:true,childList:true,attributes:true,characterData:true});
 x.panel.render({...b});x.panel.render({...b});await settle();assert.equal(mutations,0);
 assert.equal(facts.firstElementChild,node);buttons.forEach(button=>assert.equal(x.document.getElementById(button.id),button));
 observer.disconnect();
});
test('heartbeat timestamp updates without log spam; session and stale transitions log exactly once',()=>{
 const x=setup();x.panel.render(bridge());const before=x.document.getElementById('sessionMiniLog').textContent;
 for(let i=1;i<=20;i++)x.panel.render(bridge({last_seen:'2026-10-24T00:00:'+String(i).padStart(2,'0')+'Z'}));
 assert.equal(x.document.getElementById('sessionMiniLog').textContent,before);
 const confirmed=bridge({tiktok_session_status:'confirmed',session_evidence:['visible_own_profile_with_avatar','visible_account_inbox']});
 x.panel.render(confirmed);x.panel.render(confirmed);
 assert.equal([...x.document.querySelectorAll('#sessionMiniLog li')].filter(n=>n.textContent.includes('Session CONFIRMED')).length,1);
 x.panel.render({...confirmed,heartbeat_fresh:false});x.panel.render({...confirmed,heartbeat_fresh:false});
 assert.equal([...x.document.querySelectorAll('#sessionMiniLog li')].filter(n=>n.textContent.includes('Heartbeat stale')).length,1);
 assert.equal(x.document.getElementById('sessionStatus').textContent,'Unknown');
 assert.ok(x.document.getElementById('sessionMiniLog').children.length<=10);
 assert.match(x.document.getElementById('sessionEvidence').textContent,/Activity: não observado/);
});
test('bounded transition log and command endpoint 404 stay visible without duplicates',()=>{
 const x=setup();x.panel.render(bridge());
 for(let i=0;i<30;i++)x.panel.log('fixture',i,'event '+i);
 assert.equal(x.document.getElementById('sessionMiniLog').children.length,10);
 x.panel.render(bridge({command_api_status:404,command_api_error:'missing'}));
 x.panel.render(bridge({command_api_status:404,command_api_error:'missing'}));
 assert.equal([...x.document.querySelectorAll('#sessionMiniLog li')].filter(n=>n.textContent.includes('/api/dev/commands/next [404]')).length,1);
 assert.equal(x.document.getElementById('connectionApiError').hidden,false);
 x.panel.render(bridge({command_api_status:200}));assert.equal(x.document.getElementById('connectionApiError').hidden,true);
});
test('connection polling is single-flight and only calls the small session endpoint',async()=>{
 const x=setup();let resolve,calls=[];
 x.context.fetch=url=>{calls.push(url);return new Promise(r=>resolve=r);};
 const p=x.panel.poll();x.panel.poll();assert.deepEqual(calls,['/api/session/state']);
 resolve({ok:true,json:async()=>({bridge:bridge()})});await p;
 assert.equal(x.panel.stats().inFlight,false);
});
test('verify logs once, does not navigate, and renewal action survives intermediate polls',async()=>{
 const x=setup(),calls=[];x.panel.render(bridge());
 x.context.fetch=async(url,options={})=>{calls.push({url,options});return {ok:true,json:async()=>url==='/api/tiktok/verify'?{id:'check',status:'UNKNOWN'}:url==='/api/tiktok/renew'?{id:'job'}:{bridge:bridge()}};};
 await x.panel.verify();assert.equal([...x.document.querySelectorAll('#sessionMiniLog li')].filter(n=>n.textContent.includes('Verificando sessão...')).length,1);
 await x.panel.renew();x.panel.render(bridge());assert.equal(x.panel.stats().action,'renewing');
 x.panel.render(bridge(),true,{renewal:{id:'job',status:'SUCCEEDED',detail:'ready'}});
 assert.equal(x.panel.stats().action,'waiting_for_login');
 assert.ok(calls.every(c=>['/api/tiktok/verify','/api/tiktok/renew','/api/session/state'].includes(c.url)));
});

test('confirmed account with active stop waits for collection recovery, not login',()=>{
 const x=setup();x.panel.setAction('waiting_for_login','old state');
 const b=bridge({tiktok_session_status:'confirmed',session_signals:{profile_route_present:true,messages_route_present:true,activity_or_inbox_present:true,authenticated_sidebar_present:true,account_avatar_present:true,following_authenticated_present:true,logged_out_cta_present:false}});
 x.panel.render(b);
 assert.equal(x.panel.stats().action,'waiting_for_collection_recovery');
 x.panel.setAction('waiting_for_login','stale action');assert.equal(x.panel.stats().action,'waiting_for_collection_recovery');
 assert.match(x.document.getElementById('sessionEvidence').textContent,/Profile: ✓/);
 assert.match(x.document.getElementById('sessionEvidence').textContent,/Activity: ✓/);
 assert.match(x.document.querySelector('[data-connection-state="SECURITY STOP"]').textContent,/active/);
 assert.ok(x.document.getElementById('sessionSelectorDebugText'));
});

test('human connection summary uses the canonical read model while diagnostics stay available',()=>{
 const x=setup();const b=bridge({tiktok_session_status:'confirmed',security_stop_active:false});
 x.panel.render(b,true,{connection:{status:'CONNECTED',message:'Tudo pronto para usar.',tiktok:'CONNECTED',session:'CONFIRMED',browser:'ONLINE',security:'OK',mode:'SEARCH_ONLY',lastSeenSeconds:2}});
 assert.match(x.document.getElementById('connectionUserPanel').textContent,/Tudo pronto para usar/);
 assert.match(x.document.getElementById('connectionUserPanel').textContent,/Search-only/);
 assert.equal(x.document.getElementById('connectionFacts').closest('details').querySelector('summary').textContent,'Diagnóstico avançado');
 assert.ok(x.document.getElementById('verifySession'));
});

test('human connection headings do not expose Companion or raw bridge state',()=>{
 const x=setup(),b=bridge({security_stop_active:false});
 for(const [connection,title] of [
  [{status:'ATTENTION',title:'TikTok não encontrado',message:'Abra o TikTok no Chrome conectado à Babi.',tiktok:'NOT_FOUND',session:'UNCONFIRMED',browser:'ONLINE',security:'OK',mode:'SEARCH_ONLY'},'TikTok não encontrado'],
  [{status:'ATTENTION',title:'Login necessário',message:'Faça login manualmente no TikTok.',tiktok:'CONNECTED',session:'LOGGED_OUT',browser:'ONLINE',security:'OK',mode:'SEARCH_ONLY'},'Login necessário'],
  [{status:'BLOCKED',title:'Ação necessária',message:'Resolva a verificação manualmente.',tiktok:'CONNECTED',session:'UNCONFIRMED',browser:'ONLINE',security:'BLOCKED',mode:'SEARCH_ONLY'},'Ação necessária'],
  [{status:'DISCONNECTED',title:'Navegador desconectado',message:'A Babi não está recebendo comunicação da extensão.',tiktok:'NOT_FOUND',session:'UNCONFIRMED',browser:'OFFLINE',security:'OK',mode:'SEARCH_ONLY'},'Navegador desconectado']
 ]){x.panel.render(b,true,{connection});assert.equal(x.document.querySelector('[data-connection-title]').textContent,title);}
 assert.equal(x.document.querySelector('[data-connection-actions]').textContent.includes('RENOVAR'),false);
});
