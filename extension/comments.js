/* Observational sampling only. The sole click opens the fixed comments section.
 * Never activates like/reply/expand-replies/follow/share/save/composer controls. */
(() => {
  'use strict';
  const VERSION='tiktok-comments-visible-v2';
  const ROWS='[data-e2e="comment-level-1"],[data-e2e="comment-level-2"],[data-e2e="comment-item"],[data-comment-id]';
  const TEXT='[data-e2e="comment-text"],[data-e2e="comment-content"],[data-e2e="comment-text-content"],[data-e2e="comment-level-1-text"],[data-e2e="comment-level-2-text"]';
  const PANELS='[data-e2e="comment-list"],[data-e2e="comment-list-container"],[data-e2e="comment-container"],[data-e2e="comments-list"]';
  const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));

  function assertPage(doc,win,url) {
    globalThis.ProductHunterSafety?.assertSafe(doc);
    const expected=ProductHunterSearch.videoUrl(url,url),actual=ProductHunterSearch.videoUrl(doc.location.href,doc.location.href);
    if (!expected || !actual || expected.split('/').at(-1)!==actual.split('/').at(-1)) throw new Error('Comments video identity changed');
    const challenge=doc.querySelector('[id*="captcha"],iframe[src*="captcha"],[class*="captcha-verify"],[data-e2e="login-modal"]');
    if (challenge && ProductHunterSearch.visible(challenge,win)) throw new Error('Login/security challenge visible; human intervention required');
    return actual;
  }
  function rowFor(seed) {
    if (seed.matches('p,span') && !seed.querySelector(TEXT)) {
      for(let row=seed.parentElement,depth=0;row && depth<3;row=row.parentElement,depth++) {
        if (['BODY','MAIN','HTML'].includes(row.tagName)) break;
        if (row.querySelectorAll(ROWS).length>1) break;
        if (row.querySelector('a[href*="/@"],[data-e2e="comment-reply-1"],[data-e2e="comment-reply-2"]')) return row;
      }
    }
    return seed;
  }
  function own(node,row) {
    for(let parent=node.parentElement;parent && parent!==row;parent=parent.parentElement) {
      if (parent.matches(ROWS)) return false;
    }
    return true;
  }
  function local(row,selectors,win) {
    return [...row.querySelectorAll(selectors)].filter(node=>own(node,row) && ProductHunterSearch.visible(node,win));
  }
  function rowText(row,seed,win) {
    const parts=[];
    function walk(node) {
      if(node.nodeType===3) {parts.push(node.textContent);return;}
      if(node.nodeType!==1 || !ProductHunterSearch.visible(node,win) ||
          node.matches('script,style,input,textarea,form,[contenteditable="true"]')) return;
      if(node!==row && node!==seed && node.matches(ROWS) && !node.contains(seed)) return;
      for(const child of node.childNodes) walk(child);
    }
    walk(row);return parts.join(' ').replace(/\s+/g,' ').trim().slice(0,6000);
  }
  function extractComment(row,position,win,seed=row) {
    const {text,visible,parseViews}=ProductHunterSearch;
    if (!visible(row,win)) return null;
    if(seed.matches('p[data-e2e="comment-level-1"],p[data-e2e="comment-level-2"],span[data-e2e="comment-level-1"],span[data-e2e="comment-level-2"]') && !visible(seed,win)) return null;
    let texts=local(row,TEXT,win);
    if (!texts.length && seed.matches('p[data-e2e="comment-level-1"],p[data-e2e="comment-level-2"],span[data-e2e="comment-level-1"],span[data-e2e="comment-level-2"]') && visible(seed,win)) texts=[seed];
    if (!texts.length) {
      const paragraphs=local(row,'p',win).filter(node=>!node.closest('a,button,[role="button"],[data-e2e^="comment-username"],[data-e2e^="comment-reply"]') && !node.querySelector('a[href*="/@"],button,input,textarea'));
      if (paragraphs.length===1) texts=paragraphs;
    }
    if (texts.length!==1) return null;
    const value=text(texts[0],win,4000);
    if (!value) return null;
    let author=null;
    for (const anchor of local(row,'a[href]',win)) {
      if (texts[0].contains(anchor)) continue;
      try {
        const url=new URL(anchor.getAttribute('href'),row.ownerDocument.location.href);
        if (url.protocol==='https:' && ['www.tiktok.com','tiktok.com'].includes(url.host) && !url.username && !url.password && /^\/@[A-Za-z0-9._]+\/?$/.test(url.pathname)) {
          author=url.pathname.slice(1).replace(/\/$/,'');break;
        }
      } catch {}
    }
    let identifier=row.getAttribute('data-comment-id') || seed.getAttribute('data-comment-id') || null;
    const domId=row.getAttribute('id') || seed.getAttribute('id') || '';
    if (!identifier && /^comment[-_]\d+$/.test(domId)) identifier=domId.replace(/^comment[-_]/,'');
    if (identifier && !/^[A-Za-z0-9_-]{1,128}$/.test(identifier)) identifier=null;
    const likesNode=local(row,'[data-e2e="comment-like-count"],[data-e2e="comment-digg-count"]',win)[0];
    let likesRaw=likesNode?text(likesNode,win,100):null;
    if (likesRaw && !/\d/.test(likesRaw)) likesRaw=null;
    let likesAccessible=null;
    if(likesRaw===null) {
      const controls=local(row,'[role="button"][aria-label],button[aria-label]',win)
        .filter(node=>/curtidas?|likes?/i.test(node.getAttribute('aria-label')||'') && !node.matches('[data-e2e^="comment-reply"]'));
      const candidates=[];
      for(const control of controls) {
        const spans=local(control,'span',win).map(node=>text(node,win,100)).filter(raw=>parseViews(raw)!==null);
        const label=control.getAttribute('aria-label');
        const tokens=[...label.matchAll(/\d+(?:[.,]\d+)*(?:\s*[KMB])?/gi)].map(match=>match[0]);
        const raw=spans.length===1?spans[0]:tokens.length===1 && parseViews(tokens[0])!==null?tokens[0]:null;
        if(raw!==null) candidates.push({raw,label,value:parseViews(raw)});
      }
      if(candidates.length && new Set(candidates.map(candidate=>candidate.value)).size===1) {
        likesRaw=candidates[0].raw;likesAccessible=candidates[0].label;
      }
    }
    let timestampNode=local(row,'time,[data-e2e="comment-time"],[data-e2e="comment-date"]',win)[0];
    if(!timestampNode) {
      const reply=local(row,'[data-e2e="comment-reply-1"],[data-e2e="comment-reply-2"]',win)[0];
      for(let node=reply,depth=0;node && node!==row && depth<3;node=node.parentElement,depth++) {
        const sibling=node.previousElementSibling;
        if(!sibling || !sibling.matches('span,time') || !visible(sibling,win)) continue;
        const value=text(sibling,win,200);
        if(value && /^(?:(?:\d{4}[-/])?\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?|(?:h[áa]|hace)?\s*\d+\s*(?:s|min|m|h|d|w|wk|mo|y|seg|dias?|horas?|semanas?|meses?|años?)(?:\s*(?:ago|atr[áa]s))?|agora|ontem|hoje|now|just now|yesterday|today|ayer|hoy)$/iu.test(value)) {timestampNode=sibling;break;}
      }
    }
    const timestamp=timestampNode?text(timestampNode,win,200):null;
    const replyNode=local(row,'[data-e2e="comment-reply-expand"],[data-e2e="view-more-replies"]',win)[0];
    const replyText=replyNode?text(replyNode,win,200):null;
    const match=replyText?.match(/(?:view|ver|see|mostrar)?\s*(\d+)\s*(?:replies|respostas|respuestas)/i);
    const isReply=seed.matches('[data-e2e="comment-level-2"]') || !!seed.closest('[data-e2e="comment-level-2"]') ? true
      : seed.matches('[data-e2e="comment-level-1"]') ? false : null;
    return {comment_id:identifier,author_username:author,text:value,likes:parseViews(likesRaw),likes_raw:likesRaw,
      timestamp,position,is_reply:isReply,reply_count:match?Number(match[1]):null,
      source:'comments_visible',raw_visible_text:(rowText(row,seed,win)+(likesAccessible?' | likes aria-label: '+likesAccessible:'')).slice(0,6000),
      extraction_method:'semantic_comment_row',confidence:.95,extractor_version:VERSION};
  }
  function rows(doc,win) {
    const seen=new Set(),result=[];
    for(const seed of doc.querySelectorAll(ROWS)) {
      const row=rowFor(seed);
      if(seen.has(row)) continue;
      seen.add(row);
      const value=extractComment(row,result.length+1,win,seed);
      if(value) result.push({row,value,seed});
    }
    return result.sort((a,b)=>{
      const x=a.row.getBoundingClientRect(),y=b.row.getBoundingClientRect();
      return x.top-y.top || x.left-y.left;
    });
  }
  function panel(doc,win) {
    const explicit=[...doc.querySelectorAll(PANELS)].find(node=>ProductHunterSearch.visible(node,win));
    if(explicit) return explicit;
    const first=rows(doc,win)[0]?.row;
    for(let node=first?.parentElement,depth=0;node && depth<6;node=node.parentElement,depth++) {
      if(['BODY','HTML','MAIN'].includes(node.tagName)) break;
      if(node.querySelector('video,[data-e2e="video-desc"]')) break;
      if(node.scrollHeight>node.clientHeight || node.getAttribute('role')==='list') return node;
    }
    return first?.parentElement || null;
  }
  function scrollRegion(root,win) {
    for(let node=root,depth=0;node && depth<6;node=node.parentElement,depth++) {
      if(['BODY','HTML','MAIN'].includes(node.tagName)) break;
      if(node.querySelector('video,[data-e2e="video-desc"],nav')) break;
      if(node.clientHeight>0 && node.scrollHeight>node.clientHeight && /auto|scroll/.test(win.getComputedStyle(node).overflowY)) return node;
    }
    return null;
  }
  function key(comment) {
    return comment.comment_id?'id:'+comment.comment_id:JSON.stringify([comment.author_username,comment.text,comment.timestamp,comment.is_reply]);
  }
  async function sampleComments(options,doc=document,win=window) {
    if(!Number.isInteger(options.target_count) || options.target_count<1 || options.target_count>100) throw new Error('Comments target must be 1..100');
    const started=Date.now(),url=assertPage(doc,win,options.video_url),deadline=started+45000,diagnostics=[];
    let root=panel(doc,win),opened=false;
    const openDeadline=Date.now()+10000;
    while(!root && Date.now()<openDeadline) {
      assertPage(doc,win,url);
      if(!opened) {
        const toggle=[...doc.querySelectorAll('[data-e2e="comment-icon"],[data-e2e="browse-comment"]')]
          .find(node=>ProductHunterSearch.visible(node,win) && node.matches('button,[role="button"]') && !node.closest('form,[contenteditable="true"]'));
        if(toggle) { toggle.click(); opened=true; diagnostics.push('Opened semantic comments section; no engagement control activated'); }
      }
      await delay(600);root=panel(doc,win);
    }
    if(!root) {
      const labels=[...new Set([...doc.querySelectorAll('[data-e2e*="comment"]')].map(node=>node.getAttribute('data-e2e')))].slice(0,16);
      throw new Error('Comments region unavailable; semantic nodes: '+JSON.stringify(labels));
    }
    const found=new Map(),identities=new WeakMap();let nextIdentity=0,scrolls=0,stagnant=0,reason='time_limit';
    function stableKey(row,value) {
      if(value.comment_id) return key(value);
      let identity=identities.get(row);
      if(!identity || identity.text!==value.text || (identity.author && value.author_username && identity.author!==value.author_username)) {
        identity={key:'dom:'+nextIdentity++,text:value.text,author:value.author_username};identities.set(row,identity);
      }
      if(value.author_username) identity.author=value.author_username;
      return identity.key;
    }
    function uniqueComments() {
      // React can replace a row element while scrolling. Match the same visible
      // author/text/time/reply identity across replacements as the backend does.
      const unique=new Map();
      for(const value of found.values()) {
        const identity=key(value),previous=unique.get(identity);
        if(!previous) unique.set(identity,value);
      }
      return [...unique.values()];
    }
    while(Date.now()<deadline) {
      assertPage(doc,win,url);
      const before=uniqueComments().length;
      for(const {row,value,seed} of rows(doc,win)) {
        if(!root.contains(row) && row!==root) continue;
        const identity=stableKey(row,value),previous=found.get(identity);
        if(!previous) {
          if(found.size<2) {
            const structure=[...row.querySelectorAll('[data-e2e],time,span,button')].filter(node=>own(node,row) && ProductHunterSearch.visible(node,win)).slice(0,12)
              .map(node=>({tag:node.tagName,e2e:node.getAttribute('data-e2e'),role:node.getAttribute('role'),text:ProductHunterSearch.text(node,win,60)}));
            diagnostics.push(('Comment row DOM: '+JSON.stringify(structure)).slice(0,500));
            if(found.size===0) {
              const escape=value=>value.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
              function tree(node) {
                if(node.nodeType===3) return escape(node.textContent);
                if(node.nodeType!==1 || !ProductHunterSearch.visible(node,win) || node.matches('script,style,input,textarea,form,svg,[contenteditable="true"]')) return node.tagName==='SVG'?'<svg></svg>':'';
                if(node!==row && node!==seed && node.matches(ROWS) && !node.contains(seed)) return '';
                const tag=node.tagName.toLowerCase(),attrs=['data-e2e','role','aria-label'].filter(key=>node.getAttribute(key)).map(key=>' '+key+'="'+escape(node.getAttribute(key).slice(0,100))+'"').join('');
                return '<'+tag+attrs+'>'+[...node.childNodes].map(tree).join('')+'</'+tag+'>';
              }
              const html=tree(row).slice(0,1800);
              for(let index=0;index<html.length;index+=440) diagnostics.push('First row snapshot '+index+': '+html.slice(index,index+440));
            }
          }
          found.set(identity,{...value,position:found.size+1});
        } else {
          // Visibility of an author's link/date can change while the same row
          // crosses the viewport. This is not a second comment. Keep only
          // metadata actually observed, and preserve both local raw witnesses.
          const merged={...previous};
          for(const field of ['comment_id','author_username','likes','likes_raw','timestamp','is_reply','reply_count']) {
            if(value[field]!==null) merged[field]=value[field];
          }
          if(!merged.raw_visible_text.includes(value.raw_visible_text)) merged.raw_visible_text=(merged.raw_visible_text+'\n'+value.raw_visible_text).slice(0,6000);
          found.set(identity,merged);
        }
      }
      const total=uniqueComments().length;
      if(total>=options.target_count) {reason='target_reached';break;}
      if(total===0 && Date.now()<started+15000) {
        await delay(700);root=panel(doc,win)||root;continue;
      }
      stagnant=total===before?stagnant+1:0;
      if(stagnant>=3) {reason=total?'no_more_loaded':'empty';break;}
      const region=scrollRegion(root,win);
      if(!region) {reason=total?'no_scrollable_region':'empty';break;}
      if(scrolls>=20) {reason='scroll_limit';break;}
      // Assign only the verified comments scroller; never window/body/feed.
      region.scrollTop+=Math.max(100,Math.round(region.clientHeight*.7));scrolls++;
      await delay(1000);root=panel(doc,win)||root;
    }
    diagnostics.push(`Visible semantic rows read; ${scrolls} comments-only scroll steps`);
    return {video_url:url,target_count:options.target_count,comments:uniqueComments().slice(0,options.target_count).map((value,index)=>({...value,position:index+1})),stop_reason:reason,
      scroll_steps:scrolls,extractor_version:VERSION,diagnostics};
  }
  globalThis.ProductHunterComments=Object.freeze({extractComment,rows,sampleComments,scrollRegion});
})();
