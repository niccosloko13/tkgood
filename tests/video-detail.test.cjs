const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {domFixture} = require('./dom-fixture.cjs');

test('detail extractor reads explicit visible metadata and counts, never comment bodies or input values', () => {
  const {document, window} = domFixture(fs.readFileSync('tests/fixtures/tiktok-video-detail.html','utf8'), 'https://www.tiktok.com/@maker/video/123');
  document.readyState = 'complete';
  const context = vm.createContext({document, window, URL});
  vm.runInContext(fs.readFileSync('extension/search_results.js','utf8'), context);
  vm.runInContext(fs.readFileSync('extension/video_detail.js','utf8'), context);
  const {ready, video_detail:d} = vm.runInContext('ProductHunterDetail.extractVideoDetail()', context);
  assert.equal(ready, true);
  assert.equal(d.creator_username, '@maker');
  assert.equal(d.caption, 'Portable tool for the kitchen');
  assert.equal(d.field_evidence.likes.value, 31200);
  assert.equal(d.field_evidence.comments_count.value, 2251);
  assert.equal(d.field_evidence.favorites.value, 1400);
  assert.equal(d.field_evidence.shares.value, 83);
  assert.equal(d.views, null, 'likes must never be treated as views');
  assert.equal(d.views_raw, null);
  assert.equal(d.thumbnail_url, 'https://images.example/poster.jpg');
  assert.equal(d.field_evidence.caption.source, 'video_detail');
  assert.equal(d.extraction_version, 'tiktok-video-detail-v2');
  for (const forbidden of ['COMMENT CONTENT','INPUT','HIDDEN TEXT','UNRELATED']) {
    assert.ok(!d.raw_visible_text.includes(forbidden));
    assert.ok(!d.card_snapshot.includes(forbidden));
  }
});

test('detail extractor rejects account/settings and other non-video routes', () => {
  const {document, window} = domFixture('<html><body></body></html>', 'https://www.tiktok.com/settings');
  const context = vm.createContext({document, window, URL});
  vm.runInContext(fs.readFileSync('extension/search_results.js','utf8'), context);
  vm.runInContext(fs.readFileSync('extension/video_detail.js','utf8'), context);
  assert.throws(() => vm.runInContext('ProductHunterDetail.extractVideoDetail()', context), /public TikTok video route/);
});

test('detail creator can come from a visible profile href beside the description without a username label', () => {
  const html = '<html><body><section><a href="/@maker">Maker profile</a><div data-e2e="video-desc">Kitchen tool</div><strong data-e2e="like-count">31.2K</strong></section><a href="/@other">Unrelated</a></body></html>';
  const {document, window} = domFixture(html, 'https://www.tiktok.com/@maker/video/123');
  document.readyState = 'complete';
  const context = vm.createContext({document, window, URL});
  vm.runInContext(fs.readFileSync('extension/search_results.js','utf8'), context);
  vm.runInContext(fs.readFileSync('extension/video_detail.js','utf8'), context);
  const result = vm.runInContext('ProductHunterDetail.extractVideoDetail()', context);
  assert.equal(result.ready, true);
  assert.equal(result.video_detail.creator_username, '@maker');
  assert.equal(result.video_detail.field_evidence.creator_username.confidence, .98);
  assert.ok(!result.video_detail.raw_visible_text.includes('Unrelated'));
});

test('detail worker navigates only the requested video and waits for matching ready metadata', async () => {
  const updates = [], messages = [], posts = [], stored = {};
  let currentUrl = 'https://www.tiktok.com/search?q=home+gadgets', clock = 0;
  const event = () => ({addListener() {}});
  class FixtureDate extends Date { static now() {return clock;} }
  const context = vm.createContext({URL, AbortSignal, console, Date:FixtureDate,
    setInterval() {}, setTimeout(fn, ms) {clock += ms; queueMicrotask(fn);},
    fetch: async (url, options) => {
      const body = options.body ? JSON.parse(options.body) : null;
      if (body) posts.push({url,body});
      return {ok:true,json:async () => url.includes('/next?') ? {command:{id:1,type:'READ_VIDEO_DETAIL',query:'https://www.tiktok.com/@maker/video/123'}} : {ok:true}};
    },
    chrome:{
      runtime:{id:'ext',getManifest:() => ({version:'0.1.4'}),onMessage:event(),onInstalled:event(),onStartup:event()},
      alarms:{create:async () => {},onAlarm:event()},
      storage:{local:{set:async value => Object.assign(stored,value),get:async key => ({[key]:stored[key]}),remove:async key => {delete stored[key];}}},
      tabs:{query:async () => [{id:7,url:currentUrl}],get:async () => ({id:7,url:currentUrl,status:'complete'}),
        update:async (id, options) => {updates.push(options); currentUrl=options.url;},
        sendMessage:async (id,message) => {
          messages.push(message);
          return message.type === 'PH_READ_VIDEO_DETAIL' ? {ok:true,ready:true,video_detail:{video_url:currentUrl,video_id:'123'}} : {};
        },onRemoved:event(),onUpdated:event()}
    }
  });
  vm.runInContext(fs.readFileSync('extension/pacing.js','utf8')+fs.readFileSync('extension/search_discovery.js','utf8')+fs.readFileSync('extension/background.js','utf8'), context);
  for (let i=0;i<20;i++) await new Promise(resolve => setImmediate(resolve));
  assert.equal(updates.length,1);
  assert.equal(updates[0].url,'https://www.tiktok.com/@maker/video/123');
  assert.ok(clock >= 2000);
  assert.equal(posts.at(-1).body.status,'SUCCEEDED');
  assert.equal(posts.at(-1).body.video_detail.video_id,'123');
  assert.ok(messages.every(message => ['PH_SIGNALS','PH_READ_VIDEO_DETAIL'].includes(message.type)));
});
