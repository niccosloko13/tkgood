const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {domFixture} = require('./dom-fixture.cjs');
const {extractSearchResults} = require('../extension/search_results.js');
const html = fs.readFileSync('tests/fixtures/tiktok-search.html', 'utf8');

test('video links extracted, canonicalized and deduplicated without CSS class dependency', () => {
  const {document, window} = domFixture(html);
  const results = extractSearchResults(document, window);
  assert.equal(results.length, 2);
  assert.equal(results.linksDetected, 3);
  assert.equal(results[0].video_url, 'https://www.tiktok.com/@maker/video/123456789');
  assert.equal(results[1].video_url, 'https://www.tiktok.com/@other/video/987654321');
  assert.equal(results[0].creator_username, '@maker');
  assert.equal(results[0].creator_display_name, 'Maker Studio');
  assert.equal(results[0].caption, 'Portable home gadget');
  assert.equal(results[0].views, '1.2M');
  assert.equal(results[0].likes, '42K');
});
test('invalid URLs, hidden and offscreen cards are ignored', () => {
  const {document, window} = domFixture(html);
  const results = extractSearchResults(document, window);
  assert.deepEqual(results.map(v => new URL(v.video_url).pathname), ['/@maker/video/123456789', '/@other/video/987654321']);
  assert.ok(!results[0].raw_visible_text.includes('SECRET'));
  assert.equal(results[0].comments_count, null);
});
test('missing fields remain null, including creator when present only in URL', () => {
  const {document, window} = domFixture(html);
  const video = extractSearchResults(document, window)[1];
  for (const key of ['creator_username','creator_display_name','caption','views','likes','comments_count','shares']) assert.equal(video[key], null, key);
});
test('reject non-search pages and missing search query', () => {
  for (const page of ['https://www.tiktok.com/', 'https://evil.example/search?q=test', 'https://www.tiktok.com/search']) {
    const {document, window} = domFixture(html, page);
    assert.throws(() => extractSearchResults(document, window), /requires/);
  }
});
test('capture is bounded to at most 100 unique visible videos', () => {
  const cards = Array.from({length: 150}, (_, i) => `<article><a href="/@maker/video/${i + 1}">Video</a></article>`).join('');
  const {document, window} = domFixture(`<html><body>${cards}</body></html>`);
  assert.equal(extractSearchResults(document, window).length, 100);
});
