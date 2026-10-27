/* DOM evidence only; no remote requests, challenge solving or page mutation. */
(() => {
  let halted=null;
  const stop=value=>{halted=String(value).slice(0,500);};
  function reason(doc) {
    if(halted)return halted;
    const text=((doc.title||'')+' '+(doc.body?.innerText||doc.body?.textContent||'')).slice(0,16000);
    if(/access denied|\b403\s*(?:forbidden|access denied)|\bhttp\s*403\b/i.test(text))return 'access_denied_or_http_403';
    if(/verify (?:that )?you(?: are|'re) human|security verification|security challenge|complete the captcha/i.test(text))return 'security_challenge';
    if(doc.querySelector?.('#captcha-verify-container,iframe[src*="captcha"],[data-e2e="captcha"]'))return 'captcha';
    if(globalThis.ProductHunterSession?.read&&doc.location?.href){
      const session=ProductHunterSession.read(doc,doc.location.href);
      if(session.tiktok_session_status==='login_required')return 'confirmed_logged_out';
    }
    return null;
  }
  function assertSafe(doc) {const value=reason(doc);if(value){const e=new Error('Security stop: '+value);e.challenge=true;throw e;}}
  globalThis.ProductHunterSafety=Object.freeze({reason,assertSafe,stop});
})();
