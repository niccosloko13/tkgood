/* Pure DOM read: no clicks, scrolling, network calls or account changes. */
(() => {
  'use strict';
  const VERSION = 'tiktok-search-card-v2';
  const MAX_RESULTS = 100;
  const CAPTIONS = ['[data-e2e="search-card-video-caption"]', '[data-e2e="search-card-desc"]', '[data-e2e="video-desc"]'];
  const VIEW_COUNTS = ['[data-e2e="video-views"]', '[data-e2e="search-card-video-views"]', '[data-e2e="search-card-views"]'];

  function isCaptionContext(element) {
    if (element.closest('[data-e2e="search-card-video-caption"],[data-e2e="video-desc"],[data-e2e*="music"],[data-e2e*="audio"]')) return true;
    const desc = element.closest('[data-e2e="search-card-desc"]');
    // The live DOM uses search-card-desc for a whole metadata block containing
    // BOTH the caption and author/date. Do not classify its author as a mention.
    return !!desc && !desc.querySelector('[data-e2e="search-card-user-link"],[data-e2e="search-card-user-unique-id"],[data-e2e="search-card-user-username"]');
  }

  function captionNodes(card) {
    return CAPTIONS.flatMap(selector => [...card.querySelectorAll(selector)]).filter(node =>
      node.getAttribute('data-e2e') !== 'search-card-desc' || !node.querySelector('[data-e2e="search-card-user-link"],[data-e2e="search-card-user-unique-id"],[data-e2e="search-card-user-username"]'));
  }

  function profileLinks(card) {
    return [...card.querySelectorAll('a[href]')].filter(anchor => {
      try {
        const u = new URL(anchor.getAttribute('href'), anchor.ownerDocument.location.href);
        return u.protocol === 'https:' && ['www.tiktok.com','tiktok.com'].includes(u.host) && !u.username && !u.password && /^\/@[A-Za-z0-9._]+\/?$/.test(u.pathname)
          && !isCaptionContext(anchor);
      } catch { return false; }
    });
  }

  function videoUrl(href, base) {
    try {
      const u = new URL(href, base);
      if (u.protocol !== 'https:' || u.username || u.password || !['www.tiktok.com', 'tiktok.com'].includes(u.host) ||
          !/^\/@[A-Za-z0-9._]+\/video\/[0-9]+\/?$/.test(u.pathname)) return null;
      return 'https://www.tiktok.com' + u.pathname.replace(/\/$/, '');
    } catch { return null; }
  }

  function visible(element, win) {
    if (!element || element.nodeType !== 1) return false;
    for (let node = element; node; node = node.parentElement) {
      const style = win.getComputedStyle(node);
      if (node.hidden || node.getAttribute('aria-hidden') === 'true' || style.display === 'none' ||
          style.visibility === 'hidden' || style.visibility === 'collapse' || style.opacity === '0') return false;
    }
    const r = element.getBoundingClientRect();
    let left = Math.max(0, r.left), top = Math.max(0, r.top);
    let right = Math.min(win.innerWidth, r.right), bottom = Math.min(win.innerHeight, r.bottom);
    for (let node = element.parentElement; node; node = node.parentElement) {
      const style = win.getComputedStyle(node);
      const box = node.getBoundingClientRect();
      if (/(hidden|clip|scroll|auto)/.test(style.overflowX)) { left = Math.max(left, box.left); right = Math.min(right, box.right); }
      if (/(hidden|clip|scroll|auto)/.test(style.overflowY)) { top = Math.max(top, box.top); bottom = Math.min(bottom, box.bottom); }
    }
    return r.width > 0 && r.height > 0 && right > left && bottom > top;
  }

  function text(element, win, max = 4000) {
    if (!visible(element, win)) return null;
    const parts = [];
    function walk(node) {
      if (node.nodeType === 3) { parts.push(node.textContent); return; }
      if (node.nodeType !== 1 || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(node.tagName) || !visible(node, win)) return;
      for (const child of node.childNodes) walk(child);
    }
    walk(element);
    return parts.join(' ').replace(/\s+/g, ' ').trim().slice(0, max) || null;
  }

  function findResultCard(anchor) {
    const base = anchor.ownerDocument.location.href;
    const stable = anchor.closest('[data-e2e="search_top-item"], [data-e2e="search-card"], [data-e2e="search-video-item"], [data-e2e="search-card-container"], article');
    const identities = element => new Set([...element.querySelectorAll('a[href*="/video/"]')]
      .map(a => videoUrl(a.getAttribute('href'), base)?.split('/').at(-1)).filter(Boolean));
    let card = stable && identities(stable).size === 1 ? stable : anchor;
    // Real TikTok search_top-item is a MEDIA tile (role=button), not necessarily
    // the full result. Include its sibling metadata within ONE video identity.
    // An explicit article is already a logical boundary, even if metadata is absent.
    if (card.tagName === 'ARTICLE') return card;
    for (let level = 0, parent = card.parentElement; level < 6 && parent; level++, parent = parent.parentElement) {
      if (['BODY', 'HTML', 'MAIN'].includes(parent.tagName) || ['list', 'grid', 'feed'].includes(parent.getAttribute('role'))) break;
      if (parent.querySelector('nav,aside,header,form,[role="navigation"]') || identities(parent).size !== 1) break;
      card = parent;
      if (card.tagName === 'ARTICLE' || (profileLinks(card).length && card.querySelector(CAPTIONS.join(',')))) break;
    }
    return card;
  }

  function geometry(element) {
    const rect = element.getBoundingClientRect();
    return Object.fromEntries(['top','bottom','left','right'].map(key => [key, Math.round(rect[key] * 10) / 10]));
  }

  function cardDiagnostics(card, win) {
    const summarize = nodes => ({candidates: nodes.length, visible: nodes.filter(node => visible(node, win)).length,
      rects: nodes.slice(0, 3).map(geometry)});
    return {viewport: {width: win.innerWidth, height: win.innerHeight}, card_rect: geometry(card),
      creator: summarize([...new Set([...profileLinks(card), ...card.querySelectorAll('[data-e2e="search-card-user-unique-id"],[data-e2e="search-card-user-username"]')])]),
      caption: summarize(captionNodes(card)),
      views: summarize([...card.querySelectorAll(VIEW_COUNTS.join(','))])};
  }

  function firstText(card, selectors, win, max) {
    for (const selector of selectors) {
      for (const node of card.querySelectorAll(selector)) {
        const value = text(node, win, max);
        if (value) return value;
      }
    }
    return null;
  }

  function parseViews(raw) {
    if (typeof raw !== 'string') return null;
    let value = raw.trim().replace(/\u00a0/g, ' ')
      .replace(/^(?:views|visualiza[çc][õo]es)\s*:?\s*/i, '').replace(/\s+(?:views|visualiza[çc][õo]es)$/i, '');
    let integer;
    if (/^\d+$/.test(value)) integer = BigInt(value);
    else if (/^\d{1,3}([., ])\d{3}(?:\1\d{3})*$/.test(value)) integer = BigInt(value.replace(/[., ]/g, ''));
    else {
      const match = value.match(/^(\d+)(?:[.,](\d+))?\s*([KMB])$/i);
      if (!match) return null;
      const fraction = match[2] || '';
      const numerator = BigInt(match[1] + fraction) * {K: 1000n, M: 1000000n, B: 1000000000n}[match[3].toUpperCase()];
      const divisor = 10n ** BigInt(fraction.length);
      if (numerator % divisor) return null;
      integer = numerator / divisor;
    }
    return integer <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(integer) : null;
  }

  function imageUrl(value, base) {
    try { const u = new URL(value, base); return u.protocol === 'https:' && !u.username && !u.password ? u.href : null; }
    catch { return null; }
  }

  function thumbnail(card, win, base, anchor) {
    const covers = [...card.querySelectorAll('[data-e2e="search-card-video-cover"], [data-e2e="video-cover"]')];
    const roots = [anchor, ...covers].filter(Boolean);
    const images = [...new Set(roots.flatMap(root => ['IMG','VIDEO'].includes(root.tagName) ? [root] : [...root.querySelectorAll('img,video')]))];
    for (const image of images) {
      if (!visible(image, win)) continue;
      for (const value of [image.currentSrc, image.getAttribute('src'), image.getAttribute('poster')]) {
        if (!value || (image.tagName === 'VIDEO' && value !== image.getAttribute('poster'))) continue;
        const url = imageUrl(value, base);
        if (url) return url;
      }
    }
    for (const element of roots) {
      if (!visible(element, win)) continue;
      const match = win.getComputedStyle(element).backgroundImage?.match(/^url\(["']?(.+?)["']?\)$/);
      if (match) { const url = imageUrl(match[1], base); if (url) return url; }
    }
    return null;
  }

  function sanitizeCard(card, win) {
    const esc = s => String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
    const tags = new Set(['ARTICLE','DIV','SPAN','P','A','STRONG','B','EM','H2','H3','H4','SECTION','FIGURE','FIGCAPTION']);
    let budget = 12000;
    function walk(node) {
      if (budget <= 0) return '';
      if (node.nodeType === 3) { const value = esc(node.textContent).slice(0, budget); budget -= value.length; return value; }
      if (node.nodeType !== 1 || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|FORM|INPUT|TEXTAREA|SELECT|IFRAME|SVG)$/.test(node.tagName) || !visible(node, win)) return '';
      const tag = tags.has(node.tagName) ? node.tagName.toLowerCase() : 'span';
      const attrs = ['data-e2e', 'role'].map(name => {
        const value = node.getAttribute(name);
        return value && /^[a-zA-Z0-9_-]{1,80}$/.test(value) ? ` ${name}="${esc(value)}"` : '';
      }).join('');
      const start = `<${tag}${attrs}>`, end = `</${tag}>`;
      budget -= start.length + end.length;
      return start + [...node.childNodes].map(walk).join('') + end;
    }
    return walk(card).slice(0, 12000) || null;
  }

  function extractSearchResultCard(card, position, anchor = null) {
    const doc = card.ownerDocument, win = doc.defaultView, base = doc.location.href;
    anchor ||= [...card.querySelectorAll('a[href*="/video/"]')].find(a => videoUrl(a.getAttribute('href'), base) && visible(a, win));
    if (!anchor && card.tagName === 'A') anchor = card;
    const canonical = anchor && videoUrl(anchor.getAttribute('href'), base);
    if (!canonical) throw new Error('Card has no valid video anchor');
    const evidence = {};
    function record(field, value, confidence, source = 'search_card', raw = null) {
      if (value !== null) evidence[field] = {value, confidence, source, observed_at: null, ...(raw !== null ? {raw_value: raw} : {})};
      return value;
    }
    const video_id = canonical.split('/').at(-1);
    record('video_url', canonical, 1); record('video_id', video_id, 1);
    let username = null;
    for (const profile of profileLinks(card)) {
      if (!visible(profile, win)) continue;
      try {
        const url = new URL(profile.getAttribute('href'), base);
        if (url.protocol !== 'https:' || !['www.tiktok.com','tiktok.com'].includes(url.host) || url.username || url.password || !/^\/@[A-Za-z0-9._]+\/?$/.test(url.pathname)) continue;
        username = record('creator_username', url.pathname.replace(/^\//, '').replace(/\/$/, ''), .98);
        break;
      } catch { /* Not reliable creator evidence. */ }
    }
    if (!username) {
      const value = firstText(card, ['[data-e2e="search-card-user-unique-id"]', '[data-e2e="search-card-user-username"]'], win, 256);
      if (value && /^@?[A-Za-z0-9._]+$/.test(value)) username = record('creator_username', value.startsWith('@') ? value : '@' + value, .95);
    }
    if (!username) {
      for (const node of card.querySelectorAll('span,p')) {
        if (isCaptionContext(node)) continue;
        const value = text(node, win, 256);
        if (value && /^@[A-Za-z0-9._]+$/.test(value)) { username = record('creator_username', value, .7, 'heuristic_text'); break; }
      }
    }
    const display = record('creator_display_name', firstText(card, ['[data-e2e="search-card-user-nickname"]', '[data-e2e="search-card-user-name"]'], win, 512), .95);
    let caption = captionNodes(card).map(node => text(node, win, 4000)).find(Boolean) || null;
    if (caption) record('caption', caption, .95);
    else {
      // Text on a dedicated video-title link/heading is local evidence. Never
      // treat the full card text, audio, username or counts as a caption.
      const candidates = [...card.querySelectorAll('a[href*="/video/"], h2, h3, [role="heading"]')];
      if (card.tagName === 'A') candidates.unshift(card);
      for (const node of candidates) {
        if (node.querySelector('img,video,[data-e2e="video-views"],[data-e2e="like-count"]') || node.closest('[data-e2e*="music"], [data-e2e*="audio"]')) continue;
        if (node.closest('[data-e2e*="user"], [data-e2e*="creator"]')) continue;
        const linked = node.closest('a[href]');
        if (linked && !videoUrl(linked.getAttribute('href'), base)) continue;
        const value = text(node, win, 4000);
        if (value && value.length >= 6 && /\p{L}/u.test(value) && !/^[@#]/.test(value) && parseViews(value) === null) {
          caption = record('caption', value, .75, 'heuristic_text'); break;
        }
      }
    }
    const views_raw = firstText(card, VIEW_COUNTS, win, 100);
    const views = record('views', parseViews(views_raw), .98, 'search_card', views_raw);
    const thumbnail_url = record('thumbnail_url', thumbnail(card, win, base, anchor), .95);
    const metricRaw = {
      likes: firstText(card, ['[data-e2e="like-count"]', '[data-e2e="search-card-like-count"]'], win, 100),
      comments_count: firstText(card, ['[data-e2e="comment-count"]'], win, 100),
      shares: firstText(card, ['[data-e2e="share-count"]'], win, 100),
      favorites: firstText(card, ['[data-e2e="favorite-count"]', '[data-e2e="collect-count"]'], win, 100)
    };
    for (const [name, raw] of Object.entries(metricRaw)) {
      if (raw === null) continue;
      const value = parseViews(raw);
      evidence[name] = {value, raw_value: raw, confidence: value === null ? 0 : .98, source: 'search_card', observed_at: null};
    }
    const result = {
      video_id, video_url: canonical, creator_username: username, creator_display_name: display,
      caption, views_raw, views, thumbnail_url, search_position: position,
      ...metricRaw,
      raw_visible_text: text(card, win, 10000), card_snapshot: sanitizeCard(card, win),
      card_diagnostics: cardDiagnostics(card, win),
      extraction_version: VERSION, field_evidence: evidence
    };
    result.extraction_completeness = ['video_url','video_id','creator_username','caption','views','thumbnail_url'].filter(k => result[k] !== null).length / 6;
    return result;
  }

  function extractSearchResults(doc = document, win = window, limit = MAX_RESULTS) {
    const page = new URL(doc.location.href);
    if (page.origin !== 'https://www.tiktok.com' || page.pathname.replace(/\/$/, '') !== '/search' || !page.searchParams.get('q')?.trim()) {
      throw new Error('READ_SEARCH_RESULTS requires the current TikTok search page');
    }
    const results = new Map(), anchors = [];
    let detected = 0, invalid = 0, attempted = 0;
    for (const anchor of doc.querySelectorAll('a[href*="/video/"]')) {
      const url = videoUrl(anchor.getAttribute('href'), page.href);
      if (!visible(anchor, win)) continue;
      if(limit !== MAX_RESULTS && attempted >= limit)break;
      attempted++;
      if(!url){invalid++;continue;}
      detected++;
      anchors.push({anchor, url, rect: anchor.getBoundingClientRect()});
    }
    anchors.sort((a,b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left);
    for (const {anchor, url} of anchors) {
      const identity = url.split('/').at(-1);
      if (results.has(identity) || results.size >= limit) continue;
      results.set(identity, extractSearchResultCard(findResultCard(anchor), results.size + 1, anchor));
    }
    const items = [...results.values()];
    Object.defineProperty(items, 'linksDetected', {value: detected});
    Object.defineProperty(items, 'invalidDetected', {value: invalid});
    return items;
  }

  const api = {extractSearchResults, findResultCard, extractSearchResultCard, parseViews, visible, text, videoUrl};
  globalThis.ProductHunterSearch = Object.freeze(api);
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
