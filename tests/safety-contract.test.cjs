const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const gate=require('../extension/safety_gate.js'),contract=JSON.parse(fs.readFileSync('config/safety_contract.json','utf8'));
test('browser and shared contract expose exactly the same canonical states',()=>{
 assert.equal(gate.version,contract.version);assert.deepEqual(gate.page_states,contract.page_states);assert.deepEqual(gate.security_states,contract.security_states);
});
test('canonical Safety blocks hard events, holds loading, and permits only healthy confirmed evidence',()=>{
 const healthy={current_page_status:'healthy',page_ready_state:'complete',tiktok_session_status:'confirmed'};
 assert.equal(gate.observation(healthy).may_continue,true);
 for(const e of [{current_page_status:'challenge'},{current_page_status:'http_403'},{security_stop:'CAPTCHA'},{tiktok_session_status:'login_required'},{session_signals:{logged_out_cta_present:true}}])assert.equal(gate.observation(e).may_continue,false);
 assert.equal(gate.observation({page_ready_state:'loading'}).transient,true);
 assert.equal(gate.observation(healthy,{global_stopped:true}).security,'GLOBAL_BLOCKED');
 assert.equal(gate.observation(healthy,{pending_targets:true}).may_continue,false);
 assert.equal(gate.observation(healthy,{target_blocked:true}).security,'TARGET_BLOCKED');
});
