const {test}=require('node:test'),assert=require('node:assert/strict');
const {target,create}=require('../extension/target_security.js');
const URL='https://www.tiktok.com/@maker/video/123';
function harness({stored={},result={classification:'TARGET_BLOCK',blocked_targets:[],target_security_pending:false},fail=false}={}){
 const calls=[],stops=[];
 const chrome={runtime:{id:'ext'},storage:{local:{get:async keys=>Object.fromEntries((Array.isArray(keys)?keys:[keys]).map(k=>[k,stored[k]])),set:async values=>Object.assign(stored,values)}}};
 const api=create({chrome,request:async(path,body)=>{calls.push({path,body});if(fail)throw Error('offline');return path.endsWith('blocked-targets')?{items:result.blocked_targets,pending:result.target_security_pending}:result;},stopForSecurity:async reason=>stops.push(reason)});
 return {api,calls,stops,stored};
}
test('isolated 403 persists local quarantine before reporting; no navigation capability',async()=>{
 const h=harness({result:{classification:'TARGET_PENDING_HEALTH',blocked_targets:[{url:URL,status:'BLOCKED'}],target_security_pending:true}});
 await h.api.http403(URL+'?token=secret');assert.equal(h.stops.length,0);assert.equal(await h.api.isHolding(),true);
 assert.equal(h.stored.blockedTargets[0].url,URL);assert.ok(!JSON.stringify(h.calls).includes('secret'));
 const count=h.calls.length;await assert.rejects(h.api.assertAllowed(URL),/TARGET_PREVIOUSLY_BLOCKED/);assert.equal(h.calls.length,count);
 await h.api.sync({blocked_targets:h.stored.blockedTargets,target_security_pending:false});assert.equal(await h.api.isHolding(),false);
});
test('historically blocked target skips without request',async()=>{
 const h=harness({stored:{failedVideoUrls:[URL]}});
 await assert.rejects(h.api.assertAllowed(URL+'?tracking=x'),/TARGET_PREVIOUSLY_BLOCKED/);assert.equal(h.calls.length,0);
});

test('temporary challenge-context quarantine skips without request or revalidation',async()=>{
 const h=harness({stored:{blockedTargets:[{url:URL,status:'TEMPORARILY_QUARANTINED',reason:'CHALLENGE_TRIGGER_CONTEXT'}]}});
 await assert.rejects(h.api.assertAllowed(URL),/TARGET_PREVIOUSLY_BLOCKED/);assert.equal(h.calls.length,0);
});
test('backend quarantine checked before individual open, unrelated target allowed',async()=>{
 const h=harness({result:{blocked_targets:[{url:URL,status:'BLOCKED'}],target_security_pending:false}});
 await assert.rejects(h.api.assertAllowed(URL),/TARGET_PREVIOUSLY_BLOCKED/);
 await h.api.assertAllowed('https://www.tiktok.com/@other/video/124');assert.equal(h.stops.length,0);
});
test('lost reporting holds navigation with durable outbox',async()=>{
 const h=harness({fail:true});await assert.rejects(h.api.http403(URL));assert.equal(await h.api.isHolding(),true);
 assert.equal(h.stored.target403Outbox.length,1);await assert.rejects(h.api.assertAllowed(URL),/TARGET_PREVIOUSLY_BLOCKED/);
});
test('home/search/challenge 403 remain global',async()=>{
 for(const path of ['/','/search?q=home','/challenge','/captcha','/verify','/login']){
  const h=harness();await h.api.http403('https://www.tiktok.com'+path);assert.equal(h.stops.length,1);assert.equal(h.calls.length,0);
 }
 assert.equal(target('https://evil.com/@maker/video/123'),null);
});

test('a target blocked during cooldown is never opened',async()=>{
 const vm=require('node:vm'),fs=require('node:fs');let blocked=false,opens=0;
 const source=fs.readFileSync('extension/background.js','utf8');
 const start=source.indexOf('async function updateTab('),end=source.indexOf('async function prepareExistingTab(',start);
 const context=vm.createContext({assertSafe:async()=>{},PH_TARGET_SAFETY:{assertAllowed:async()=>{if(blocked)throw Error('TARGET_PREVIOUSLY_BLOCKED');}},ProductHunterPacing:{sleep:async()=>{blocked=true;}},pacing:{cooldownMs:2500},chrome:{tabs:{get:async()=>({url:'https://www.tiktok.com/'}),update:async()=>{opens++;}}}});
 vm.runInContext(source.slice(start,end),context);
 await assert.rejects(vm.runInContext(`updateTab(7,{url:'${URL}'})`,context),/TARGET_PREVIOUSLY_BLOCKED/);
 assert.equal(opens,0);
});
