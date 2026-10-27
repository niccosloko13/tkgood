/* Explicit READ ONLY detail command. No click, scroll, comments, hidden state or network. */
(() => {
  'use strict';
  const METRICS = {
    views:{counts:['browse-view-count','view-count','video-view-count','video-views'],actions:[],label:/views?|visualiza[çc][õo]es/i},
    likes:{counts:['browse-like-count','like-count'],actions:['like-icon','browse-like'],label:/likes?|curtidas?/i},
    comments_count:{counts:['browse-comment-count','comment-count'],actions:['comment-icon','browse-comment'],label:/comments?|coment[áa]rios?/i},
    shares:{counts:['browse-share-count','share-count'],actions:['share-icon','browse-share'],label:/shares?|compartilhamentos?/i},
    favorites:{counts:['browse-collect-count','favorite-count','collect-count'],actions:['favorite-icon','collect-icon','browse-collect'],label:/favorites?|favourites?|favoritos?|collections?/i}
  };
  const selector = names => names.map(name=>`[data-e2e="${name}"]`).join(',');

  function parseMetricText(raw, name, parse) {
    if (!raw) return null;
    raw = raw.replace(/\s+/g,' ').trim();
    const direct = /^\d[\d.,\u00a0 ]*(?:[KMB])?$/i.test(raw) ? parse(raw) : null;
    if (direct !== null) return {raw, value:direct};
    if (/^\d[\d.,\u00a0 ]*(?:[A-Z]{1,2})?$/.test(raw)) return {raw,value:null};
    if (!METRICS[name].label.test(raw)) return null;
    const tokens = [...raw.matchAll(/\d+(?:[.,\u00a0 ]\d+)*(?:\s*[KMB])?/gi)];
    if (tokens.length !== 1) return null;
    const token = tokens[0][0].trim(), value = parse(token);
    const before = raw.slice(0,tokens[0].index), after = raw.slice(tokens[0].index+tokens[0][0].length);
    // Reject unknown suffixes, dates/times and digit-bearing words. Labels stay
    // in audit evidence, never in raw_value or the numeric field.
    if (/[\p{L}\d/:]$/u.test(before) || /^[\p{L}\d/:]/u.test(after)) return null;
    return value === null ? null : {raw:token,value};
  }

  function extractVisibleMetric(doc, win, name) {
    const {visible,text,parseViews} = ProductHunterSearch, config = METRICS[name];
    const countCandidates = [...doc.querySelectorAll(selector(config.counts))];
    const countNodes = countCandidates.filter(node=>visible(node,win));
    const actionNodes = config.actions.length ? [...doc.querySelectorAll(selector(config.actions))].filter(node=>visible(node,win)) : [];
    const roots = new Set(actionNodes), candidates=[], audit=[];
    const otherSelectors=selector(Object.entries(METRICS).filter(([field])=>field!==name).flatMap(([,value])=>[...value.counts,...value.actions]));
    const forbiddenScope='input,textarea,form,[data-e2e="comment-list"],[data-e2e="comment-level-1"],[data-e2e="video-desc"],a[href*="/video/"]';
    const auditText = (method, raw) => {
      if (raw && audit.length<10) audit.push({method,text:raw.slice(0,180)});
    };
    function candidate(node, raw, method, confidence, priority) {
      if (!visible(node,win)) return;
      auditText(method,raw);
      const parsed=parseMetricText(raw,name,parseViews);
      if (parsed) candidates.push({...parsed,method,confidence:parsed.value===null?0:confidence,priority});
    }
    for (const node of countNodes) {
      candidate(node,text(node,win,180),'semantic_text',.98,4);
      for (const child of node.querySelectorAll('span,strong,small')) candidate(child,text(child,win,180),'semantic_text',.98,4);
      // Find a small action-local region. Stop before another metric, a card,
      // account form, comment list or any page container.
      let region=node.parentElement;
      for (let depth=0; region && depth<2; depth++,region=region.parentElement) {
        if (['BODY','HTML','MAIN','ASIDE','ARTICLE','SECTION'].includes(region.tagName) ||
            region.querySelector(otherSelectors+','+forbiddenScope)) break;
        roots.add(region);
      }
    }
    for (const root of roots) {
      if (!visible(root,win) || root.querySelector(otherSelectors+','+forbiddenScope)) continue;
      candidate(root,text(root,win,180),'action_text',.94,3);
      for (const child of root.querySelectorAll('span,strong,small')) candidate(child,text(child,win,180),'adjacent_text',.90,3);
    }
    const localNodes = new Set([...countNodes,...[...roots].filter(root=>visible(root,win) && !root.querySelector(otherSelectors+','+forbiddenScope))]);
    for (const root of [...localNodes]) for (const child of root.querySelectorAll('[aria-label],[aria-valuetext],[aria-valuenow],span,strong,small')) localNodes.add(child);
    for (const node of localNodes) {
      if (!visible(node,win)) continue;
      for (const attr of ['aria-label','aria-valuetext','aria-valuenow']) candidate(node,node.getAttribute(attr),'aria_label',.95,2);
      for (const pseudo of ['::before','::after']) {
        const style=win.getComputedStyle(node,pseudo), content=style.content;
        if (!content || ['none','normal','""'].includes(content) || style.display==='none' || style.visibility==='hidden' || style.opacity==='0') continue;
        if (content.startsWith('"') && content.endsWith('"')) {
          try { candidate(node,JSON.parse(content),'generated_content',.95,3); } catch {}
        }
      }
    }
    const numeric = candidates.filter(item=>item.value!==null);
    const available = numeric.length ? numeric : candidates;
    const top = available.length ? Math.max(...available.map(item=>item.priority)) : 0;
    const best = available.filter(item=>item.priority===top);
    const values = new Set(best.map(item=>item.value));
    const chosen = values.size===1 ? best[0] : null;
    return {raw:chosen?.raw??null,value:chosen?.value??null,method:chosen?.method??null,
      confidence:chosen?.confidence??0,audit, candidate_nodes:countCandidates.length,visible_nodes:countNodes.length+actionNodes.length,
      ambiguous:values.size>1};
  }
  function extractVideoDetail(doc = document, win = window) {
    const {videoUrl, visible, text} = ProductHunterSearch;
    const canonical = videoUrl(doc.location.href, doc.location.href);
    if (!canonical) throw new Error('Expected the current public TikTok video route');
    const fields = {}, evidence = {}, selected = [];
    function first(selectors, max = 4000) {
      for (const selector of selectors) for (const node of doc.querySelectorAll(selector)) {
        if (!visible(node, win)) continue;
        const value = text(node, win, max);
        if (value !== null) { selected.push({selector, value}); return {node, value}; }
      }
      return null;
    }
    function record(name, value, confidence, raw = null) {
      fields[name] = value;
      if (value !== null) evidence[name] = {value, confidence, source:'video_detail', observed_at:null, ...(raw !== null ? {raw_value:raw} : {})};
      return value;
    }
    record('video_url', canonical, 1);
    record('video_id', canonical.split('/').at(-1), 1);
    const desc = first(['[data-e2e="browse-video-desc"]','[data-e2e="video-desc"]','[data-e2e="video-description"]']);
    const author = first(['[data-e2e="browse-username"]','[data-e2e="video-author-uniqueid"]'], 256);
    let username = null;
    if (author) {
      const link = author.node.closest('a[href]') || author.node.querySelector('a[href]');
      if (link) {
        try {
          const url = new URL(link.getAttribute('href'), doc.location.href);
          if (url.protocol === 'https:' && url.host === 'www.tiktok.com' && !url.username && !url.password && /^\/@[A-Za-z0-9._]+\/?$/.test(url.pathname)) username = url.pathname.slice(1).replace(/\/$/, '');
        } catch {}
      }
      if (!username && /^@?[A-Za-z0-9._]+$/.test(author.value)) username = author.value.startsWith('@') ? author.value : '@' + author.value;
    }
    // The URL is a cross-check only, never a source for a missing creator.
    const routeCreator = new URL(canonical).pathname.split('/')[1];
    // Current detail layout may place its profile href beside the description
    // without a dedicated username label. Stay in that local metadata region.
    if (!username && desc) {
      let region = desc.node.parentElement;
      for (let depth = 0; region && depth < 5; depth++, region = region.parentElement) {
        if (['BODY','HTML','MAIN'].includes(region.tagName)) break;
        const videos = [...region.querySelectorAll('a[href*="/video/"]')]
          .map(node => videoUrl(node.getAttribute('href'), doc.location.href)).filter(Boolean);
        if (videos.some(url => url.split('/').at(-1) !== fields.video_id)) break;
        for (const link of region.querySelectorAll('a[href]')) {
          if (!visible(link, win)) continue;
          try {
            const url = new URL(link.getAttribute('href'), doc.location.href);
            if (url.protocol === 'https:' && url.host === 'www.tiktok.com' && !url.username && !url.password &&
                /^\/@[A-Za-z0-9._]+\/?$/.test(url.pathname) &&
                url.pathname.replace(/\/$/,'').slice(1).toLowerCase() === routeCreator.toLowerCase()) {
              username = url.pathname.replace(/\/$/,'').slice(1);
              selected.push({selector:'description-local-profile-href', value:username});
              break;
            }
          } catch {}
        }
        if (username) break;
      }
    }
    if (username && username.toLowerCase() !== routeCreator.toLowerCase()) username = null;
    record('creator_username', username, .98);
    const nickname = first(['[data-e2e="browse-nickname"]','[data-e2e="video-author-nickname"]'], 512);
    record('creator_display_name', nickname?.value || null, .95);
    record('caption', desc?.value || null, .95);
    let metricCount = 0, numericCount=0;
    const metricDiagnostics={};
    for (const name of Object.keys(METRICS)) {
      const metric=extractVisibleMetric(doc,win,name), {raw,value,confidence,method}=metric;
      if (metric.visible_nodes) metricCount++;
      if (value!==null) numericCount++;
      metricDiagnostics[name]={value,raw,method,candidate_nodes:metric.candidate_nodes,visible_nodes:metric.visible_nodes,ambiguous:metric.ambiguous};
      selected.push({selector:`metric:${name}`,value:JSON.stringify({metric:name,...metric})});
      if (name === 'views') { fields.views_raw = raw; fields.views=value; }
      else {
        fields[name] = raw;
      }
      if (raw !== null) evidence[name] = {value, raw_value:raw, confidence, source:'video_detail', observed_at:null,method};
    }
    let thumbnail = null;
    for (const video of doc.querySelectorAll('video[poster]')) {
      if (!visible(video, win)) continue;
      try {
        const url = new URL(video.getAttribute('poster'), doc.location.href);
        if (url.protocol === 'https:' && !url.username && !url.password) { thumbnail = url.href; break; }
      } catch {}
    }
    record('thumbnail_url', thumbnail, .95);
    const escape = s => s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    const snapshot = '<section>' + selected.map(item => `<p>${escape(item.value)}</p>`).join('') + '</section>';
    const result = {...fields, search_position:null, extraction_version:'tiktok-video-detail-v2', field_evidence:evidence,
      raw_visible_text:selected.map(item => item.value).join(' | ').slice(0,10000) || null,
      card_snapshot:snapshot.slice(0,12000), card_diagnostics:null};
    result.extraction_completeness = ['video_url','video_id','creator_username','caption','views','thumbnail_url'].filter(k => result[k] !== null).length / 6;
    return {ready:doc.readyState === 'complete' && !!username && metricCount > 0, video_detail:result,
      diagnostics:{ready_state:doc.readyState, creator_found:!!username, metric_count:metricCount,
        viewport:{width:win.innerWidth,height:win.innerHeight},document_visibility:doc.visibilityState,
        numeric_metric_count:numericCount,metrics:metricDiagnostics,
        captcha_present:!!doc.querySelector('[id*="captcha"],iframe[src*="captcha"],[class*="captcha-verify"]'),
        matched_selectors:[...new Set(selected.map(item => item.selector))]}};
  }
  globalThis.ProductHunterDetail = Object.freeze({extractVideoDetail,extractVisibleMetric});
  if (typeof module !== 'undefined' && module.exports) module.exports = {extractVideoDetail,extractVisibleMetric};
})();
