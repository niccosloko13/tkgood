/* Live account DOM evidence only. Never cookies, page mutation or navigation.
   Persistent security latch is deliberately NOT an authentication signal. */
(() => {
  function visible(node) {
    if(!node || node.hidden || node.closest?.('[hidden],[aria-hidden="true"]'))return false;
    const rect=node.getBoundingClientRect(),style=node.ownerDocument.defaultView.getComputedStyle(node);
    return rect.width>0&&rect.height>0&&style.display!=='none'&&style.visibility!=='hidden'&&style.opacity!=='0';
  }
  function pageBlocker(doc){
    const text=((doc.title||'')+' '+(doc.body?.innerText||doc.body?.textContent||'')).slice(0,16000);
    if(/access denied|\b403\s*(?:forbidden|access denied)|\bhttp\s*403\b/i.test(text))return 'access_denied_or_http_403';
    if(/verify (?:that )?you(?: are|'re) human|security verification|security challenge|complete the captcha/i.test(text))return 'security_challenge';
    if(doc.querySelector('#captcha-verify-container,iframe[src*="captcha"],[data-e2e="captcha"]'))return 'captcha';
    return null;
  }
  function read(doc,href){
    const debug={};
    const route=n=>{try{const u=new URL(n.getAttribute('href'),href);return u.origin==='https://www.tiktok.com'?u.pathname:null;}catch{return null;}};
    function signal(name,selector,predicate=()=>true){
      const all=[...doc.querySelectorAll(selector)].filter(predicate),shown=all.filter(visible),sample=shown[0]||all[0];
      debug[name]={selector,matched_count:all.length,visible_count:shown.length,
        sample_href:sample?.hasAttribute('href')?route(sample):null,sample_aria:sample?.getAttribute('aria-label')?.slice(0,160)||null,sample_data_e2e:sample?.getAttribute('data-e2e')||null};
      return shown;
    }
    const profiles=signal('profile_route_present','a[data-e2e="nav-profile"],a[data-e2e="profile-icon"],[data-e2e="profile-icon"] a[href],nav a[data-e2e*="profile"],[role="navigation"] a[data-e2e*="profile"]',n=>/^\/@[\w.]+\/?$/.test(route(n)||''));
    const messages=signal('messages_route_present','[data-e2e="nav-messages"],a[href="/messages"],a[href="/messages/"],a[href="https://www.tiktok.com/messages"],[data-e2e="message-icon"]');
    const activity=signal('activity_or_inbox_present','[data-e2e="nav-activity"],[data-e2e="inbox-icon"],a[href="/activity"],a[href="/inbox"]');
    const avatars=signal('account_avatar_present','a[data-e2e="nav-profile"] img,a[data-e2e="nav-profile"] image,[data-e2e="profile-icon"] img,[data-e2e="profile-icon"] image,[data-e2e="account-avatar"]');
    const following=signal('following_authenticated_present','a[data-e2e="following-user-button"][href]',n=>/^\/@[\w.]+\/?$/.test(route(n)||'')&&Boolean(n.closest('ul,ol,[role="list"]')));
    const login=signal('logged_out_cta_present','[data-e2e="top-login-button"],[data-e2e="nav-login-button"],[data-e2e="login-modal"],[data-e2e="login-button"],[data-e2e="sidebar-login-button"],a[href="/login"],a[href^="/login?"]');
    let sidebar=null;
    if(profiles.length&&(messages.length||activity.length)){
      for(let n=profiles[0].parentElement,depth=0;n&&depth<8&&n!==doc.body;n=n.parentElement,depth++){
        if([...messages,...activity].some(control=>n.contains(control))&&n.querySelector('[data-e2e="nav-following"],[data-e2e="nav-foryou"]')){sidebar=n;break;}
      }
    }
    debug.authenticated_sidebar_present={selector:'shared navigation ancestor: nav-profile + nav-messages/nav-activity + nav-following/nav-foryou',matched_count:sidebar?1:0,visible_count:sidebar&&visible(sidebar)?1:0,
      sample_href:null,sample_aria:sidebar?.getAttribute('aria-label')||null,sample_data_e2e:sidebar?.getAttribute('data-e2e')||null};
    const signals={profile_route_present:profiles.length>0,messages_route_present:messages.length>0,activity_or_inbox_present:activity.length>0,
      authenticated_sidebar_present:Boolean(sidebar&&visible(sidebar)),account_avatar_present:avatars.length>0,following_authenticated_present:following.length>0,logged_out_cta_present:login.length>0};
    // Profile/avatar are one evidence family; messages/activity are another.
    // Composite sidebar is context, not a third independent vote.
    const groups=[(signals.profile_route_present||signals.account_avatar_present)&&'account_identity',
      (signals.messages_route_present||signals.activity_or_inbox_present)&&'account_communication',signals.following_authenticated_present&&'followed_accounts'].filter(Boolean);
    const blocker=pageBlocker(doc),shell=[...doc.querySelectorAll('main,[role="main"],[data-e2e="recommend-list-item-container"]')].some(visible);
    const page=blocker?(/403|access_denied/.test(blocker)?'http_403':'challenge'):doc.readyState==='complete'&&shell?'healthy':'unknown';
    const confirmed=page==='healthy'&&groups.length>=2&&!signals.logged_out_cta_present;
    const evidence=[];
    // Preserve positive partial evidence even when the complete session is unknown.
    if(signals.profile_route_present&&signals.account_avatar_present)evidence.push('visible_own_profile_with_avatar');
    if(signals.messages_route_present||signals.activity_or_inbox_present)evidence.push('visible_account_inbox');
    return {current_page_status:page,tiktok_session_status:signals.logged_out_cta_present?'login_required':confirmed?'confirmed':'unconfirmed',
      session_evidence:evidence,session_signals:signals,session_debug:debug,session_auth_groups:groups,session_detector_version:'dom-v2',live_page_blocker:blocker};
  }
  globalThis.ProductHunterSession=Object.freeze({read});
})();
