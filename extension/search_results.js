/* Pure DOM read: no clicks, scrolling, network calls or account changes. */
(() => {
  'use strict';
  const VERSION = 'search-dom-v1';
  const MAX_RESULTS = 100;

  function videoUrl(href, base) {
    try {
      const u = new URL(href, base);
      if (u.protocol !== 'https:' || !['www.tiktok.com', 'tiktok.com'].includes(u.host) ||
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

  function cardFor(anchor, base) {
    const stable = anchor.closest('[data-e2e="search_top-item"], [data-e2e="search-card"], [data-e2e="search-video-item"], [data-e2e="search-card-container"], article');
    if (stable) {
      const urls = new Set([...stable.querySelectorAll('a[href*="/video/"]')].map(a => videoUrl(a.getAttribute('href'), base)).filter(Boolean));
      if (urls.size === 1) return stable;
    }
    // Fallback: bounded ancestor walk, stopping before a multi-video container.
    let card = anchor;
    for (let level = 0, parent = anchor.parentElement; level < 5 && parent; level++, parent = parent.parentElement) {
      if (['BODY', 'HTML', 'MAIN'].includes(parent.tagName)) break;
      const urls = new Set([...parent.querySelectorAll('a[href*="/video/"]')].map(a => videoUrl(a.getAttribute('href'), base)).filter(Boolean));
      if (urls.size !== 1) break;
      card = parent;
    }
    return card;
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

  function extractSearchResults(doc = document, win = window) {
    const page = new URL(doc.location.href);
    if (page.origin !== 'https://www.tiktok.com' || page.pathname.replace(/\/$/, '') !== '/search' || !page.searchParams.get('q')?.trim()) {
      throw new Error('READ_SEARCH_RESULTS requires the current TikTok search page');
    }
    const results = new Map();
    let detected = 0;
    for (const anchor of doc.querySelectorAll('a[href*="/video/"]')) {
      const url = videoUrl(anchor.getAttribute('href'), page.href);
      if (!url || !visible(anchor, win)) continue;
      detected++;
      if (results.has(url) || results.size >= MAX_RESULTS) continue;
      const card = cardFor(anchor, page.href);
      let username = firstText(card, ['[data-e2e="search-card-user-unique-id"]', '[data-e2e="search-card-user-username"]'], win, 256);
      if (!username) {
        for (const profile of card.querySelectorAll('a[href]')) {
          const value = text(profile, win, 256);
          if (!value || !/^@[A-Za-z0-9._]+$/.test(value)) continue;
          try {
            const target = new URL(profile.getAttribute('href'), page.href);
            if (target.origin === page.origin && /^\/@[A-Za-z0-9._]+\/?$/.test(target.pathname)) { username = value; break; }
          } catch { /* Invalid profile links are not evidence. */ }
        }
      }
      results.set(url, {
        video_url: url,
        creator_username: username,
        creator_display_name: firstText(card, ['[data-e2e="search-card-user-nickname"]', '[data-e2e="search-card-user-name"]'], win, 512),
        caption: firstText(card, ['[data-e2e="search-card-video-caption"]', '[data-e2e="search-card-desc"]', '[data-e2e="video-desc"]'], win, 4000),
        views: firstText(card, ['[data-e2e="video-views"]', '[data-e2e="search-card-video-views"]'], win, 100),
        likes: firstText(card, ['[data-e2e="like-count"]', '[data-e2e="search-card-like-count"]'], win, 100),
        comments_count: firstText(card, ['[data-e2e="comment-count"]'], win, 100),
        shares: firstText(card, ['[data-e2e="share-count"]'], win, 100),
        raw_visible_text: text(card, win, 10000),
        extraction_version: VERSION
      });
    }
    const items = [...results.values()];
    Object.defineProperty(items, 'linksDetected', {value: detected});
    return items;
  }

  globalThis.ProductHunterSearch = Object.freeze({extractSearchResults});
  if (typeof module !== 'undefined' && module.exports) module.exports = {extractSearchResults};
})();
