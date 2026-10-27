const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {parseHTML} = require('linkedom');

test('dashboard capture button sends semantic command and refreshes count, recent videos and safe OPEN link', async () => {
  const html = fs.readFileSync('app/static/index.html', 'utf8');
  const {document, window} = parseHTML(html);
  let captured = false;
  let sampled = false;
  const calls = [];
  const video = {video_id:'123',video_url: 'https://www.tiktok.com/@maker/video/123', creator_username: '@maker',
    creator_display_name: null, caption: '<img src=x onerror=alert(1)> useful gadget', views: '1.2M',
    search_query: 'home gadgets', collected_at: '2026-10-21T12:00:00+00:00'};
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const context = vm.createContext({document, URL, console, setInterval() {}, setTimeout() {}, alert: message => {throw new Error(message);},
    fetch: async (url, options = {}) => {
      calls.push({url, options});
      let response;
      if (url === '/api/status') response = {bridge: {extension_connected: true, chrome_connected: true, tiktok_open: true,
        authenticated_hint: true, url: 'https://www.tiktok.com/search?q=home+gadgets', page_signals: {content_script_connected: true}}};
      else if (url === '/api/commands' && options.method === 'POST') {
        const body=JSON.parse(options.body);
        if(body.type==='READ_COMMENTS_SAMPLE') {
          assert.deepEqual(body,{type:'READ_COMMENTS_SAMPLE',video_url:video.video_url,target_count:30});sampled=true;
        } else {assert.deepEqual(body, {type: 'READ_SEARCH_RESULTS'}); captured = true;}
        response = {id: 2, status: 'PENDING'};
      } else if (url === '/api/commands') response = {items: captured ? [{id: 2, type: 'READ_SEARCH_RESULTS', status: 'SUCCEEDED', query: 'home gadgets', detail: '1 visible unique results read'}] : [{id: 1, type: 'SEARCH', status: 'SUCCEEDED', query: 'home gadgets'}]};
      else if (url === '/api/videos/recent') response = {total: captured ? 1 : 0, items: captured ? [video] : []};
      else if (url === '/api/comments/summaries') response={items:sampled?[{video_id:'123',stop_reason:'target_reached',extractor_version:'tiktok-comments-visible-v1',signals:{comments_sampled:30,unique_commenters:29,comments_with_question_mark:11,comments_with_price_terms:6,comments_with_link_terms:9,comments_with_buy_terms:7,comments_with_problem_terms:1,duplicate_ratio:0}}]:[]};
      else if (url === '/api/product-candidates') response={items:[]};
      else if (url === '/api/creators') response={items:[]};
      else if (url === '/api/extraction/quality') response = {capture_id: captured ? 'command:2' : null, query:'home gadgets', total: captured ? 1 : 0,
        library_total: captured ? 1 : 0, current_capture: captured ? 1 : 0, new_this_capture: captured ? 1 : 0, updated_duplicates: 0,
        coverage:{video_url:100,video_id:100,creator:100,caption:100,views:100,thumbnail:0}, complete:1,partial:0,minimal:0,thresholds_met:false,extractor_version:'tiktok-search-card-v2'};
      else if (url === '/api/events') response = {items: captured ? [{created_at: video.collected_at, event_type: 'capture', message: 'Capture completed'}] : []};
      else throw new Error('Unexpected request ' + url);
      return {ok: true, json: async () => response};
    }
  });
  vm.runInContext(script, context);
  const settle = async () => {for (let i = 0; i < 10; i++) await new Promise(resolve => setImmediate(resolve));};
  await settle();
  assert.equal(document.getElementById('videosCount').textContent, '0');
  assert.equal(document.getElementById('captureButton').disabled, false);
  document.getElementById('captureButton').dispatchEvent(new window.Event('click'));
  await settle();
  assert.equal(document.getElementById('videosCount').textContent, '1');
  assert.equal(document.getElementById('currentCaptureCount').textContent, '1');
  assert.equal(document.getElementById('newCaptureCount').textContent, '1');
  assert.equal(document.getElementById('updatedCaptureCount').textContent, '0');
  assert.match(document.getElementById('recentVideos').textContent, /@maker/);
  assert.match(document.getElementById('recentVideos').textContent, /home gadgets/);
  assert.match(document.getElementById('captureInfo').textContent, /SUCCEEDED/);
  assert.equal(document.getElementById('recentVideos').querySelectorAll('img').length, 0);
  const open = document.getElementById('recentVideos').querySelector('a');
  assert.equal(open.href, video.video_url);
  assert.equal(open.target, '_blank');
  assert.equal(open.rel, 'noopener noreferrer');
  assert.match(document.getElementById('log').textContent, /Capture completed/);
  assert.match(document.getElementById('extractionQuality').textContent, /100%/);
  assert.equal(calls.filter(c => c.options.method === 'POST').length, 1);
  document.querySelector('[data-sample-video]').dispatchEvent(new window.Event('click',{bubbles:true}));
  await settle();
  assert.match(document.getElementById('recentVideos').textContent,/Comments sampled: 30/);
  assert.match(document.getElementById('recentVideos').textContent,/Question signals: 11/);
  assert.match(document.getElementById('recentVideos').textContent,/Unique commenters: 29/);
});
