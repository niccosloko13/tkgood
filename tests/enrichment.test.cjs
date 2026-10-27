const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {domFixture} = require('./dom-fixture.cjs');
const {extractSearchResults, findResultCard, extractSearchResultCard, parseViews} = require('../extension/search_results.js');
const html = fs.readFileSync('tests/fixtures/tiktok-enrichment.html', 'utf8');

test('views formats use exact deterministic arithmetic, including decimal comma and unknown formats', () => {
  for (const [raw, expected] of JSON.parse(fs.readFileSync('tests/fixtures/view-formats.json', 'utf8'))) assert.equal(parseViews(raw), expected, String(raw));
});
test('logical card boundaries isolate creator, caption and views from misleading surrounding text', () => {
  const {document, window} = domFixture(html);
  const results = extractSearchResults(document, window);
  assert.equal(results.length, 8);
  assert.equal(results.linksDetected, 9);
  const first = results[0];
  assert.equal(first.video_id, '1001');
  assert.equal(first.creator_username, '@alpha');
  assert.equal(first.creator_display_name, 'Alpha Studio');
  assert.equal(first.caption, 'First useful home gadget');
  assert.equal(first.views, 83100);
  assert.equal(first.views_raw, '83.1K');
  assert.equal(first.thumbnail_url, 'https://images.example/alpha.jpg');
  assert.equal(first.extraction_completeness, 1);
  assert.equal(first.field_evidence.creator_username.confidence, .98);
  assert.equal(first.field_evidence.caption.source, 'search_card');
  assert.equal(first.field_evidence.views.raw_value, '83.1K');
  assert.equal(first.extraction_version, 'tiktok-search-card-v2');
  for (const result of results) {
    assert.ok(!result.raw_visible_text.includes('MISLEADING'));
    assert.ok(!result.raw_visible_text.includes('not_the_creator'));
  }
  assert.equal(results[1].creator_username, null);
  assert.equal(results[1].views, 1400000);
  assert.equal(results[2].caption, null, 'profile heading and audio must not become caption');
  assert.equal(results[3].creator_username, '@delta');
  assert.equal(results[3].thumbnail_url, 'https://images.example/delta.jpg');
  assert.equal(results[4].creator_username, '@epsilon');
  assert.equal(results[4].field_evidence.creator_username.source, 'heuristic_text');
  assert.equal(results[4].field_evidence.caption.confidence, .75);
  assert.equal(results[4].views, null);
  assert.equal(results[4].views_raw, 'unrecognized');
  assert.equal(results[5].creator_username, '@zeta', 'caption mentions must not replace author');
  assert.equal(results[6].views, 0);
  assert.equal(results[6].thumbnail_url, null);
  assert.deepEqual(results.map(r => r.search_position), [1,2,3,4,5,6,7,8]);
});
test('card detector and single-card extractor can be tested independently', () => {
  const {document} = domFixture(html);
  const anchor = document.querySelector('a[href*="/video/1001"]');
  const card = findResultCard(anchor);
  assert.equal(card.tagName, 'ARTICLE');
  const result = extractSearchResultCard(card, 3);
  assert.equal(result.search_position, 3);
  assert.equal(result.video_id, '1001');
});
test('sanitized snapshots exclude hidden text, scripts, credentials, URLs and event attributes', () => {
  const {document, window} = domFixture(html);
  const first = document.querySelector('article');
  first.setAttribute('onclick', 'doNotStoreThis()');
  const snapshot = extractSearchResults(document, window)[0].card_snapshot;
  assert.match(snapshot, /data-e2e="search_top-item"/);
  for (const forbidden of ['HIDDEN SECRET','do-not-store','doNotStoreToken','onclick','https://','value=']) assert.ok(!snapshot.includes(forbidden), forbidden);
});
test('visual ordering sorts visible anchors by position, not incidental DOM insertion order', () => {
  const {document, window} = domFixture(html);
  const original = window.HTMLElement.prototype.getBoundingClientRect;
  window.HTMLElement.prototype.getBoundingClientRect = function () {
    const rect = original.call(this);
    const article = this.closest('article');
    if (!article) return rect;
    const index = [...document.querySelectorAll('article')].indexOf(article);
    return {...rect, top: 100 - index * 10, bottom: 200 - index * 10};
  };
  assert.equal(extractSearchResults(document, window)[0].video_id, '1008');
});

test('profile avatar must not be mistaken for the video thumbnail', () => {
  const {document, window} = domFixture(html);
  const profile = document.createElement('a');
  profile.setAttribute('href', '/@alpha');
  profile.innerHTML = '<img src="https://images.example/avatar.jpg">';
  const card = document.querySelector('article');
  card.insertBefore(profile, card.firstChild);
  assert.equal(extractSearchResults(document, window)[0].thumbnail_url, 'https://images.example/alpha.jpg');
});

test('real media-tile shape expands to local sibling metadata without crossing into another video', () => {
  const {document, window} = domFixture(fs.readFileSync('tests/fixtures/tiktok-media-tile.html', 'utf8'));
  const firstAnchor = document.querySelector('a[href*="/video/101"]');
  const card = findResultCard(firstAnchor);
  assert.equal(card.getAttribute('data-e2e'), null, 'search_top-item is only the media container');
  assert.equal(card.querySelectorAll('a[href*="/video/"]').length, 1);
  const results = extractSearchResults(document, window);
  assert.equal(results.length, 2);
  assert.equal(results[0].creator_username, '@first');
  assert.equal(results[0].caption, 'First card description');
  assert.equal(results[0].views, 31200);
  assert.equal(results[0].likes, null, 'Mais curtidos badge is not a like count');
  for (const video of results) assert.ok(!video.raw_visible_text?.includes('GLOBAL WRONG'));
});

test('diagnostics distinguish offscreen views from a missing DOM field, without collecting offscreen values', () => {
  const {document, window} = domFixture(fs.readFileSync('tests/fixtures/tiktok-media-tile.html', 'utf8'));
  const result = extractSearchResults(document, window)[1];
  assert.equal(result.views, null);
  assert.equal(result.views_raw, null);
  assert.equal(result.creator_username, null);
  assert.equal(result.caption, null);
  assert.equal(result.card_diagnostics.views.candidates, 1);
  assert.equal(result.card_diagnostics.views.visible, 0);
  assert.ok(result.card_diagnostics.views.rects[0].top >= result.card_diagnostics.viewport.height);
  assert.ok(!result.card_snapshot.includes('OFFSCREEN'));
  assert.ok(!result.card_snapshot.includes('1.4M'));
});

test('only visible metric labels receive normalized metric evidence', () => {
  const {document, window} = domFixture(fs.readFileSync('tests/fixtures/tiktok-search.html', 'utf8'));
  const first = extractSearchResults(document, window)[0];
  assert.equal(first.field_evidence.likes.value, 42000);
  assert.equal(first.field_evidence.likes.raw_value, '42K');
  assert.equal(first.field_evidence.likes.source, 'search_card');
  assert.equal(first.field_evidence.likes.confidence, .98);
  assert.equal(first.comments_count, null);
  assert.equal(first.favorites, null);
  assert.equal(first.field_evidence.comments_count, undefined);
  assert.equal(first.field_evidence.favorites, undefined);
});

test('actual search-card-desc metadata wrapper is not itself a caption or a reason to reject its author', () => {
  const {document, window} = domFixture(fs.readFileSync('tests/fixtures/tiktok-live-metadata.html', 'utf8'));
  const results = extractSearchResults(document, window);
  assert.equal(results[0].creator_username, '@real_handle', 'href must win over display alias');
  assert.equal(results[0].field_evidence.creator_username.confidence, .98);
  assert.equal(results[0].caption, 'A practical tool #gadgets @mentioned');
  assert.ok(!results[0].caption.includes('Display Alias'));
  assert.ok(!results[0].caption.includes('2025-1-22'));
  assert.equal(results[1].creator_username, '@other');
  assert.equal(results[1].caption, null, 'author/date block is not a description');
  assert.equal(results[0].card_diagnostics.creator.visible, 2);
});
