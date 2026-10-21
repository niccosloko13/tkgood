const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {parseHTML} = require('linkedom');

test('dashboard capture button sends semantic command and refreshes count, recent videos and safe OPEN link', async () => {
  const html = fs.readFileSync('app/static/index.html', 'utf8');
  const {document, window} = parseHTML(html);
  let captured = false;
  const calls = [];
  const video = {video_url: 'https://www.tiktok.com/@maker/video/123', creator_username: '@maker',
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
        assert.deepEqual(JSON.parse(options.body), {type: 'READ_SEARCH_RESULTS'});
        captured = true;
        response = {id: 2, status: 'PENDING'};
      } else if (url === '/api/commands') response = {items: captured ? [{id: 2, type: 'READ_SEARCH_RESULTS', status: 'SUCCEEDED', query: 'home gadgets', detail: '1 visible unique results read'}] : [{id: 1, type: 'SEARCH', status: 'SUCCEEDED', query: 'home gadgets'}]};
      else if (url === '/api/videos/recent') response = {total: captured ? 1 : 0, items: captured ? [video] : []};
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
  assert.match(document.getElementById('recentVideos').textContent, /@maker/);
  assert.match(document.getElementById('recentVideos').textContent, /home gadgets/);
  assert.match(document.getElementById('captureInfo').textContent, /SUCCEEDED/);
  assert.equal(document.getElementById('recentVideos').querySelectorAll('img').length, 0);
  const open = document.getElementById('recentVideos').querySelector('a');
  assert.equal(open.href, video.video_url);
  assert.equal(open.target, '_blank');
  assert.equal(open.rel, 'noopener noreferrer');
  assert.match(document.getElementById('log').textContent, /Capture completed/);
  assert.equal(calls.filter(c => c.options.method === 'POST').length, 1);
});
