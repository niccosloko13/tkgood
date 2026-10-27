/* Public profile header only. No clicks, scrolling, external requests or engagement. */
(() => {
  'use strict';
  const VERSION='tiktok-creator-profile-v1';
  const EMPTY_BIOS=new Set(['no bio yet','ainda sem descrição','sem biografia ainda','sin descripción todavía','لا توجد نبذة تعريفية حتى الآن','لا توجد نبذة تعريفية بعد']);
  const fields={display_name:'[data-e2e="user-subtitle"]',bio:'[data-e2e="user-bio"]',
    followers:'[data-e2e="followers-count"]',following:'[data-e2e="following-count"]',
    total_likes:'[data-e2e="likes-count"]',video_count:'[data-e2e="video-count"],[data-e2e="user-video-count"]',
    profile_category:'[data-e2e="user-category"]',profile_type:'[data-e2e="user-account-type"]'};
  function profileUrl(value){
    try{const u=new URL(value);if(u.protocol!=='https:'||!['www.tiktok.com','tiktok.com'].includes(u.host)||u.username||u.password||!/^\/@[A-Za-z0-9._]{1,128}\/?$/.test(u.pathname))return null;
      return 'https://www.tiktok.com'+u.pathname.replace(/\/$/,'').toLowerCase();}catch{return null;}
  }
  function normalizeCount(raw){
    if(raw===null||raw===undefined)return null;
    const m=String(raw).trim().match(/^(\d+)(?:([.,])(\d+))?\s*([KMB])?$/i);
    if(!m||(m[2]&&!m[4]))return null;
    const fraction=m[3]||'',integer=BigInt(m[1]+fraction),scale=10n**BigInt(fraction.length);
    const value=integer*({K:1000n,M:1000000n,B:1000000000n}[(m[4]||'').toUpperCase()]||1n);
    return value%scale===0n&&value/scale<=BigInt(Number.MAX_SAFE_INTEGER)?Number(value/scale):null;
  }
  function publicLink(raw,base){
    if(typeof raw!=='string'||!raw.trim())return null;
    try{const u=new URL(raw,base);if(!['https:','http:'].includes(u.protocol)||u.username||u.password||!u.hostname||u.href.length>2048)return null;
      if([...u.searchParams.keys()].some(key=>/password|access_token|refresh_token|session|authorization|jwt/i.test(key)))return null;
      u.hash='';return u.href;}catch{return null;}
  }
  function profileRoot(title){
    if(!title)return null;
    let best=null;
    for(let node=title.parentElement,depth=0;node&&depth<7;node=node.parentElement,depth++){
      if(['BODY','HTML','MAIN'].includes(node.tagName))break;
      // Include header siblings (bio/avatar/links), but never the video grid or
      // another identity. The smallest title/count block alone can omit them.
      if(node.querySelector('nav,[role="feed"],a[href*="/video/"]')||node.querySelectorAll('[data-e2e="user-title"]').length>1)break;
      if(node.querySelector('[data-e2e="followers-count"],[data-e2e="following-count"]'))best=node;
    }
    const parent=title.closest('header,[data-e2e="user-detail"],[data-e2e="profile-header"]');
    return best||parent||title.parentElement;
  }
  function extractCreatorProfile(doc=globalThis.document,win=globalThis.window){
    const search=globalThis.ProductHunterSearch||(typeof require==='function'?require('./search_results.js'):null);
    const visible=node=>search.visible(node,win),text=node=>search.text(node,win);
    const url=profileUrl(doc.location.href);if(!url)throw new Error('Expected a public creator profile route');
    const challenges=[...doc.querySelectorAll('[id*="captcha"],iframe[src*="captcha"],[class*="captcha-verify"],[data-e2e="login-modal"]')].filter(visible);
    if(challenges.length)return {ready:false,challenge:true,diagnostics:['Visible login/security challenge; human intervention required']};
    const titles=[...doc.querySelectorAll('[data-e2e="user-title"]')],title=titles.find(visible),root=profileRoot(title);
    const headingCandidates=root?[...root.querySelectorAll('[data-e2e="user-title"],[data-e2e="user-subtitle"]')].filter(visible):[];
    // Current layouts can swap title/subtitle: match a visible heading to the
    // route, never invent the username merely from that route.
    const usernameNode=headingCandidates.find(node=>{const value=text(node);return value&&/^@?[A-Za-z0-9._]{1,128}$/.test(value)&&'https://www.tiktok.com/@'+value.replace(/^@/,'').toLowerCase()===url;});
    const rawUsername=text(usernameNode),username=rawUsername?'@'+rawUsername.replace(/^@/,'').toLowerCase():null;
    const diagnostics=[`Profile header: ${!!root}; visible username: ${!!username}; document: ${doc.readyState}; visibility: ${doc.visibilityState||'unknown'}`,
      `Username nodes: ${titles.length}; headings: ${doc.querySelectorAll('h1,h2').length}; profile count nodes: ${doc.querySelectorAll('[data-e2e="followers-count"]').length}`,
      ...headingCandidates.slice(0,2).map(node=>`Visible profile heading ${node.getAttribute('data-e2e')}: ${(text(node)||'').slice(0,150)}`),
      ...titles.slice(0,2).map(node=>{const r=node.getBoundingClientRect();return `Username rect: ${Math.round(r.x||r.left)},${Math.round(r.y||r.top)},${Math.round(r.width)},${Math.round(r.height)}`;})];
    if(!username||url!=='https://www.tiktok.com/'+username)return {ready:false,document_visibility:doc.visibilityState,diagnostics};
    const result={username,profile_url:url,...Object.fromEntries([...Object.keys(fields),'avatar_url','external_link'].map(key=>[key,null])),
      links:[],raw_visible_text:'',field_evidence:{},diagnostics,extractor_version:VERSION};
    const raw=[];
    function record(key,value,rawValue,confidence,method,normalized=null){
      result[key]=value;result.field_evidence[key]={value,raw_value:rawValue,normalized_value:normalized,source:'creator_profile',confidence,method,extractor_version:VERSION};
      if(rawValue)raw.push(key+': '+rawValue);
    }
    record('username',username,rawUsername,.99,'semantic_text');record('profile_url',url,url,.99,'profile_route');
    for(const [key,selector] of Object.entries(fields)){
      const nodes=key==='display_name'?headingCandidates.filter(node=>node!==usernameNode):[...root.querySelectorAll(selector)],node=nodes.find(visible),value=text(node);
      diagnostics.push(`${key}: ${nodes.length} candidates; ${nodes.filter(visible).length} visible`);
      if(!value)continue;
      if(key==='bio'&&EMPTY_BIOS.has(value.trim().replace(/[.!…]+$/u,'').toLowerCase())){
        raw.push('bio_placeholder: '+value);diagnostics.push('bio: explicit empty-profile placeholder; structured value null');continue;}
      if(['followers','following','total_likes','video_count'].includes(key)){const count=normalizeCount(value);record(key,count,value,.98,'semantic_text',count);}
      else record(key,value.slice(0,key==='bio'?4000:500),value.slice(0,4000),.95,'semantic_text');
    }
    let avatar=[...root.querySelectorAll('[data-e2e="user-avatar"] img,img[data-e2e="user-avatar"],img[alt="Profile photo"],img[alt="Foto de perfil"]')].find(visible),avatarMethod='visible_image';
    if(!avatar){const candidates=[...root.querySelectorAll('img')].filter(node=>{const r=node.getBoundingClientRect();return visible(node)&&!node.closest('[data-e2e="user-bio"]')&&r.width>=48&&r.height>=48&&r.width/r.height>=.8&&r.width/r.height<=1.25;});
      if(candidates.length===1){avatar=candidates[0];avatarMethod='visible_header_image';}}
    const avatarUrl=avatar&&publicLink(avatar.currentSrc||avatar.getAttribute('src'),url);
    if(avatarUrl)record('avatar_url',avatarUrl,avatarUrl,avatarMethod==='visible_image'?.98:.90,avatarMethod);
    const anchors=[...root.querySelectorAll('a[href]')];
    for(const anchor of anchors){
      if(!visible(anchor))continue;const href=publicLink(anchor.getAttribute('href'),url),label=text(anchor);
      if(!href||!label)continue;
      const parsed=new URL(href),redirect=['/link','/link/v2'].includes(parsed.pathname)&&publicLink(parsed.searchParams.get('target'),url);
      if(['www.tiktok.com','tiktok.com'].includes(parsed.hostname)&&!redirect&&!anchor.closest('[data-e2e="user-shop-link"]'))continue;
      if(result.links.some(link=>link.url===href)||result.links.length>=20)continue;
      result.links.push({url:href,label:label.slice(0,500),source:'creator_profile',confidence:.98,extractor_version:VERSION});raw.push('link: '+label+' '+href);
    }
    const external=result.links.find(link=>{const u=new URL(link.url);return !['www.tiktok.com','tiktok.com'].includes(u.hostname)||['/link','/link/v2'].includes(u.pathname);});
    if(external)record('external_link',external.url,external.url,.98,'visible_href');
    result.raw_visible_text=raw.join('\n').slice(0,10000);
    return {ready:doc.readyState==='complete',creator_profile:result,document_visibility:doc.visibilityState,diagnostics};
  }
  const api={extractCreatorProfile,normalizeCount,profileUrl,profileRoot};
  globalThis.ProductHunterCreator=Object.freeze(api);
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})();
