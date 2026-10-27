// Integration client: real extension scripts + local HTML fixture + real local API.
// No Chrome automation and no requests to TikTok or the internet.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {domFixture} = require('./dom-fixture.cjs');
const root = path.resolve(__dirname, '..');
const base = process.argv[2];
if (!/^http:\/\/127\.0\.0\.1:[0-9]+$/.test(base)) throw new Error('Only a temporary loopback API is allowed');
const fixture = process.argv.includes('--enrichment') ? 'tiktok-enrichment.html' : 'tiktok-search.html';
const {document, window} = domFixture(fs.readFileSync(path.join(__dirname, 'fixtures', fixture), 'utf8'));
document.readyState = 'complete';
if (process.argv.includes('--update')) document.querySelector('[data-e2e="video-views"]').textContent = '1.3M';
const event = () => ({addListener() {}});
let listener;
const content = vm.createContext({URL, document, window, location: document.location, setInterval() {},
  chrome: {runtime: {getManifest: () => ({version: '0.1.4'}),
    onMessage: {addListener(fn) {listener = fn;}}, sendMessage(message, callback) {callback?.();}}}
});
vm.runInContext(fs.readFileSync(path.join(root, 'extension/search_results.js'), 'utf8'), content);
vm.runInContext(fs.readFileSync(path.join(root, 'extension/content.js'), 'utf8'), content);
const stored = {};
let completed;
const done = new Promise(resolve => {completed = resolve;});
const worker = vm.createContext({URL, AbortSignal, setInterval() {},setTimeout(fn){queueMicrotask(fn);},
  fetch: async (url, options) => {
    const requestUrl = new URL(url);
    if (requestUrl.origin !== 'http://127.0.0.1:8000') throw new Error('Unexpected destination');
    const response = await fetch(base + requestUrl.pathname + requestUrl.search, options);
    if (requestUrl.pathname.endsWith('/result')) {
      process.stdout.write(JSON.stringify({http_status: response.status, body: JSON.parse(options.body)}));
      completed();
    }
    return response;
  },
  chrome: {
    runtime: {id: 'ext', getManifest: () => ({version: '0.1.4'}), onMessage: event(), onInstalled: event(), onStartup: event()},
    alarms: {create: async () => {}, onAlarm: event()},
    storage: {local: {set: async value => Object.assign(stored, value), get: async key => ({[key]: stored[key]}), remove: async key => {delete stored[key];}}},
    tabs: {query: async () => [{id: 7, url: document.location.href, title: 'TikTok'}],
      get: async () => ({id: 7, url: document.location.href,status:'complete'}),
      sendMessage: async (id, message) => new Promise(resolve => listener(message, {}, resolve)),
      update: async () => {throw new Error('Capture must never navigate');},
      onRemoved: event(), onUpdated: event()}
  }
});
vm.runInContext(fs.readFileSync(path.join(root,'extension/pacing.js'),'utf8')+fs.readFileSync(path.join(root,'extension/search_discovery.js'),'utf8')+fs.readFileSync(path.join(root, 'extension/background.js'), 'utf8'), worker);
const timer = setTimeout(() => {console.error('Capture client timed out', stored.bridgeStatus); process.exit(1);}, 12000);
done.then(() => clearTimeout(timer));
