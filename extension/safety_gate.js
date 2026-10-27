/* Adapter for config/safety_contract.json. Evidence only, no DOM or side effects. */
(() => {
 'use strict';
 const version='babi-safety-v1';
 const page_states=['HEALTHY','LOADING','CHALLENGE','LOGGED_OUT','ERROR','UNKNOWN'];
 const security_states=['OK','TARGET_BLOCKED','GLOBAL_BLOCKED'];
 function observation(b={},context={}){
  const page=b.current_page_status||'unknown',session=b.tiktok_session_status||'unconfirmed';
  const result=(page,security,may_continue,reason,transient=false)=>({page,security,session,may_continue,reason,transient,version});
  const blocker=String(b.security_stop||b.error||'');
  if(b.challenge||['challenge','http_403'].includes(page)||/403|access.denied|captcha|challenge|verify.*human/i.test(blocker))return result(page==='http_403'?'ERROR':'CHALLENGE','GLOBAL_BLOCKED',false,'SECURITY_BLOCK');
  if(['login_required','logged_out'].includes(session)||b.session_signals?.logged_out_cta_present===true)return result('LOGGED_OUT','GLOBAL_BLOCKED',false,'LOGGED_OUT');
  const state=page==='healthy'&&b.page_ready_state==='complete'?'HEALTHY':['loading','interactive'].includes(b.page_ready_state)?'LOADING':page==='error'?'ERROR':'UNKNOWN';
  if(context.global_stopped)return result(state,'GLOBAL_BLOCKED',false,'GLOBAL_SECURITY_EVENT');
  if(context.pending_targets)return result(state,'GLOBAL_BLOCKED',false,'TARGET_HEALTH_PENDING');
  if(context.target_blocked)return result(state,'TARGET_BLOCKED',false,'TARGET_PREVIOUSLY_BLOCKED');
  const allowed=state==='HEALTHY'&&session==='confirmed',transient=['LOADING','UNKNOWN'].includes(state);
  return result(state,'OK',allowed,allowed?'HEALTHY_CONFIRMED':transient?'TRANSIENT_LOADING':'SESSION_NOT_STABLE',transient);
 }
 const api=Object.freeze({version,page_states,security_states,observation});globalThis.ProductHunterSafetyGate=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})();
