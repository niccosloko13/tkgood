/* Quarantine only: no navigation, retries, clicks or page mutation. */
(() => {
 'use strict';
 function target(value){
  try{
   const u=new URL(value);
   if(u.protocol!=='https:'||!['www.tiktok.com','tiktok.com'].includes(u.hostname)||u.port||u.username||u.password)return null;
   const path=u.pathname.replace(/\/$/,'').toLowerCase();
   const target_type=/^\/@[A-Za-z0-9._]+\/video\/\d+$/.test(path)?'VIDEO':/^\/@[A-Za-z0-9._]+$/.test(path)?'CREATOR':null;
   return target_type?{target_type,url:'https://www.tiktok.com'+path}:null;
  }catch{return null;}
 }
 function create({chrome,request,stopForSecurity}){
  let holding=false;
  const denied=x=>['BLOCKED','TEMPORARILY_QUARANTINED'].includes(x.status);
  const same=(a,b)=>{const x=target(a),y=target(b);return x&&y&&(x.url===y.url||(x.target_type==='VIDEO'&&y.target_type==='VIDEO'&&x.url.split('/').at(-1)===y.url.split('/').at(-1)));};
  async function assertAllowed(value){
   const item=target(value);if(!item)return;
   const stored=await chrome.storage.local.get(['blockedTargets','failedVideoUrls']);
   const known=(stored.blockedTargets||[]).some(x=>same(x.url,item.url)&&denied(x))||(stored.failedVideoUrls||[]).some(x=>same(x,item.url));
   if(known)throw new Error('TARGET_PREVIOUSLY_BLOCKED');
   // Authoritative guard before every individual open/read, even after a restart.
   const current=await request('/api/bridge/blocked-targets');
   await chrome.storage.local.set({blockedTargets:current.items||[],targetSecurityPending:!!current.pending});
   if(current.items?.some(x=>same(x.url,item.url)&&denied(x)))throw new Error('TARGET_PREVIOUSLY_BLOCKED');
   if(current.pending)throw new Error('Target HTTP 403: waiting for passive healthy home/search');
  }
  async function isHolding(){const stored=await chrome.storage.local.get(['targetSecurityPending','target403Outbox']);return holding||!!stored.targetSecurityPending||!!stored.target403Outbox?.length;}
  async function flush(){
   const outbox=(await chrome.storage.local.get('target403Outbox')).target403Outbox||[];
   for(const event of outbox){
    const result=await request('/api/bridge/target-403',{extension_id:chrome.runtime.id,...event});
    await chrome.storage.local.set({blockedTargets:result.blocked_targets||[],targetSecurityPending:!!result.target_security_pending});
    const current=(await chrome.storage.local.get('target403Outbox')).target403Outbox||[];
    await chrome.storage.local.set({target403Outbox:current.filter(x=>x.url!==event.url||x.observed_at!==event.observed_at)});
    if(result.security_stop?.reason)await stopForSecurity(result.security_stop.reason);
   }
   holding=false;
  }
  async function http403(value){
   const item=target(value);
   if(!item){await stopForSecurity('HTTP 403: '+new URL(value).origin+new URL(value).pathname,true);return;}
   holding=true;
   const stored=await chrome.storage.local.get(['target403Outbox','blockedTargets']);
   const outbox=stored.target403Outbox||[];
   // Repeated DOM signals of the same failed document are not new attempts.
   if(!outbox.some(x=>x.url===item.url))outbox.push({url:item.url,observed_at:new Date().toISOString()});
   const blocked=stored.blockedTargets||[];
   if(!blocked.some(x=>x.url===item.url))blocked.push({...item,status:'BLOCKED',reason:'HTTP_403'});
   await chrome.storage.local.set({target403Outbox:outbox,blockedTargets:blocked,targetSecurityPending:true});
   await flush();
  }
  async function sync(heartbeat){
   if(Array.isArray(heartbeat.blocked_targets))await chrome.storage.local.set({blockedTargets:heartbeat.blocked_targets});
   if(typeof heartbeat.target_security_pending==='boolean')await chrome.storage.local.set({targetSecurityPending:heartbeat.target_security_pending});
  }
  return Object.freeze({assertAllowed,isHolding,http403,flush,sync});
 }
 const api={target,create};globalThis.ProductHunterTargetSafety=Object.freeze(api);
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})();
