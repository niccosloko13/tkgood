const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function run(command, tabs = [{id: 7, url: 'https://www.tiktok.com/', title: 'TikTok'}]) {
  const calls = [], updates = [], stored = {};
  const event = () => ({addListener() {}});
  const context = vm.createContext({
    URL, AbortSignal, console, setInterval() {},
    fetch: async (url, options) => {
      calls.push({url, body: options.body ? JSON.parse(options.body) : null});
      return {ok: true, json: async () => url.includes('/next?') ? {command} : {ok: true}};
    },
    chrome: {
      runtime: {id: 'ext', getManifest: () => ({version: '0.1.4'}), onMessage: event(), onInstalled: event(), onStartup: event()},
      alarms: {create: async () => {}, onAlarm: event()},
      storage: {local: {set: async value => Object.assign(stored, value), get: async key => ({[key]: stored[key]}), remove: async key => {delete stored[key];}}},
      tabs: {query: async () => tabs, get: async () => tabs[0], sendMessage: async () => ({authenticated_hint: true, page_ready_state: 'complete', has_search_ui: true, playback_error_visible: false}), update: async (id, value) => updates.push({id, ...value}), onRemoved: event(), onUpdated: event()}
    }
  });
  vm.runInContext(fs.readFileSync('extension/background.js', 'utf8'), context);
  for (let i = 0; i < 10; i++) await new Promise(resolve => setImmediate(resolve));
  return {calls, updates, stored};
}

test('SEARCH navigates only to fixed TikTok search route with encoded query and acknowledges', async () => {
  const {calls, updates} = await run({id: 1, type: 'SEARCH', query: 'home & gadgets #1'});
  assert.equal(updates.length, 1);
  const url = new URL(updates[0].url);
  assert.equal(url.origin, 'https://www.tiktok.com');
  assert.equal(url.pathname, '/search');
  assert.equal(url.searchParams.get('q'), 'home & gadgets #1');
  assert.equal(calls.at(-1).body.status, 'SUCCEEDED');
});
test('unsupported commands never navigate', async () => {
  for (const type of ['LIKE', 'COMMENT', 'FOLLOW', 'CLICK', 'MESSAGE', 'EDIT_SETTINGS']) {
    const {calls, updates} = await run({id: 1, type, query: 'test'});
    assert.equal(updates.length, 0);
    assert.equal(calls.at(-1).body.status, 'FAILED');
  }
});
test('extension heartbeat works without a TikTok tab and search fails safely', async () => {
  const {calls, updates} = await run({id: 1, type: 'SEARCH', query: 'test'}, []);
  assert.equal(calls[0].body.current_url, '');
  assert.equal(calls[0].body.page_title, null);
  assert.equal(calls[0].body.page_ready_state, null);
  assert.equal(updates.length, 0);
  assert.equal(calls.at(-1).body.status, 'FAILED');
});
