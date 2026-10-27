// Execute the actual content script and worker with a minimal Chrome fixture.
// stdout contains only the exact JSON body passed to fetch by background.js.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const loading = process.argv.includes('--loading');
const noTab = process.argv.includes('--no-tab');
const event = () => ({addListener() {}});
let collect;
const runtime = {
  id: 'ext', getManifest: () => ({version: '0.1.4'}),
  onMessage: {addListener(fn) {collect = fn;}},
  sendMessage(message, callback) {callback?.();},
  onInstalled: event(), onStartup: event()
};
vm.runInNewContext(fs.readFileSync(path.join(root, 'extension/content.js'), 'utf8'), {
  document: {body: loading ? null : {innerText: 'TikTok Profile Search'}, title: loading ? null : 'TikTok', readyState: loading ? 'loading' : 'complete'},
  location: {href: 'https://www.tiktok.com/'},
  chrome: {runtime}, setInterval() {}
});
let signals;
collect({type: 'PH_SIGNALS'}, {}, result => {signals = result;});
runtime.onMessage = event();
const tab = {id: 7, url: 'https://www.tiktok.com/', title: loading ? undefined : 'TikTok'};
vm.runInNewContext(fs.readFileSync(path.join(root,'extension/pacing.js'),'utf8')+fs.readFileSync(path.join(root, 'extension/background.js'), 'utf8'), {
  URL, AbortSignal, setInterval() {},
  fetch: async (url, options) => {
    if (url.endsWith('/api/bridge/heartbeat')) process.stdout.write(options.body);
    return {ok: true, json: async () => ({command: null})};
  },
  chrome: {runtime, alarms: {create: async () => {}, onAlarm: event()},
    storage: {local: {set: async () => {}, get: async () => ({})}},
    tabs: {query: async () => noTab ? [] : [tab], sendMessage: async () => loading ? undefined : signals, onRemoved: event(), onUpdated: event()}
  }
});
