/* Fixed read-only DOM inventory. No navigation, clicks, page mutation or credentials. */
(() => {
  const doc=document;
  const visible=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&!n.closest('[hidden],[aria-hidden="true"]');};
  const href=n=>{try{const u=new URL(n.getAttribute('href')||'',location.href);return u.origin===location.origin?u.pathname:null;}catch{return null;}};
  const attrs=n=>({tag:n.tagName,href:n.hasAttribute('href')?href(n):null,aria:(n.getAttribute('aria-label')||'').slice(0,160),data_e2e:n.getAttribute('data-e2e'),role:n.getAttribute('role'),id:(n.id||'').slice(0,100)});
  const sample=n=>{const r=n.getBoundingClientRect();return {...attrs(n),visible:visible(n),rect:{width:r.width,height:r.height},images:n.querySelectorAll('img,image').length,svgs:n.querySelectorAll('svg').length,
    ancestors:[n.parentElement,n.parentElement?.parentElement,n.parentElement?.parentElement?.parentElement,n.parentElement?.parentElement?.parentElement?.parentElement].filter(Boolean).map(attrs)};};
  const inspect=(selector,filter=()=>true,limit=60)=>{const all=[...doc.querySelectorAll(selector)].filter(filter);return {selector,matched_count:all.length,visible_count:all.filter(visible).length,samples:all.slice(0,limit).map(sample)};};
  return {mode:'READ_ONLY_SESSION_PROBE',url:location.href,document_ready:doc.readyState,page_title:doc.title,
    old_profile:inspect('a[data-e2e="nav-profile"],a[data-e2e="profile-icon"],[data-e2e="profile-icon"] a[href]'),
    old_messages:inspect('a[href="/messages"],a[href="/messages/"],[data-e2e="inbox-icon"],[data-e2e="message-icon"]'),
    account_routes:inspect('a[href]',n=>/^\/(?:@|messages?|inbox|activity|following|friends|upload)/.test(href(n)||''),100),
    account_controls:inspect('[data-e2e]',n=>/profile|inbox|message|activity|avatar|account|nav|sidebar|follow|friend|login|upload/i.test(n.getAttribute('data-e2e')||''),100),
    navigation:inspect('nav,aside,[role="navigation"],[data-e2e*="nav"],[data-e2e*="sidebar"]',()=>true,30),
    old_result:globalThis.ProductHunterSession?.read(doc,location.href)||null};
})();
