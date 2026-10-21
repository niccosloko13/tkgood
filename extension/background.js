const DASHBOARD = "http://127.0.0.1:8000";
const isTikTok = url => {
  try { const u = new URL(url); return u.protocol === "https:" && u.hostname === "www.tiktok.com"; }
  catch { return false; }
};
let running = false;
async function request(path, body, headers = {}) {
  const response = await fetch(DASHBOARD + path, {
    ...(body ? {method: "POST", headers: {"Content-Type": "application/json", ...headers}, body: JSON.stringify(body)} : {}),
    signal: AbortSignal.timeout(5000)
  });
  if (!response.ok) throw new Error(`Backend HTTP ${response.status}`);
  return response.json();
}
async function tick() {
  if (running) return;
  running = true;
  try {
    const tabs = (await chrome.tabs.query({url: "https://www.tiktok.com/*"})).filter(t => isTikTok(t.url));
    tabs.sort((a, b) => Number(b.active) - Number(a.active) || (b.lastAccessed || 0) - (a.lastAccessed || 0));
    const tab = tabs[0];
    let signals = {};
    if (tab) {
      try { signals = await chrome.tabs.sendMessage(tab.id, {type: "PH_SIGNALS"}); } catch { /* Reload may be needed. */ }
    }
    const payload = {
      extension_version: chrome.runtime.getManifest().version,
      current_url: tab?.url || "",
      page_title: tab?.title ?? null,
      authenticated_hint: !!signals?.authenticated_hint,
      page_ready_state: signals?.page_ready_state ?? null,
      has_search_ui: !!signals?.has_search_ui,
      playback_error_visible: !!signals?.playback_error_visible
    };
    await request("/api/bridge/heartbeat", payload, {"X-Extension-ID": chrome.runtime.id});
    await chrome.storage.local.set({bridgeStatus: {...payload, version: payload.extension_version,
      chrome_connected: true, tiktok_open: !!tab, url: payload.current_url, title: payload.page_title,
      page_signals: {content_script_connected: payload.page_ready_state !== null},
      backend_connected: true, last_seen: new Date().toISOString(), error: ""}});
    const {pendingResult} = await chrome.storage.local.get("pendingResult");
    if (pendingResult) {
      try { await request(`/api/bridge/commands/${pendingResult.id}/result`, pendingResult.body); }
      catch (err) { if (!/HTTP (404|409)/.test(String(err))) throw err; }
      await chrome.storage.local.remove("pendingResult");
    }
    const {command} = await request(`/api/bridge/commands/next?extension_id=${encodeURIComponent(chrome.runtime.id)}`);
    if (command) {
      let status = "FAILED", detail = "Unsupported command", capture = null;
      try {
        if (!['SEARCH', 'READ_SEARCH_RESULTS'].includes(command.type) || typeof command.query !== "string" || !command.query.trim() || command.query.length > 200) throw new Error("Invalid read-only command");
        if (!tab) throw new Error("TikTok tab is no longer open");
        const current = await chrome.tabs.get(tab.id);
        if (!isTikTok(current.url)) throw new Error("Target tab is no longer TikTok");
        if (command.type === 'READ_SEARCH_RESULTS') {
          const page = new URL(current.url);
          if (page.pathname.replace(/\/$/, '') !== '/search' || page.searchParams.get('q') !== command.query) throw new Error('Search page changed before capture');
          const response = await chrome.tabs.sendMessage(tab.id, {type: 'PH_READ_SEARCH_RESULTS', query: command.query});
          if (!response?.ok || !response.capture) throw new Error(response?.error || 'Reload the TikTok tab to enable capture');
          capture = response.capture;
          status = 'SUCCEEDED'; detail = `${capture.results_count} visible unique results read`;
        } else {
          const target = new URL("https://www.tiktok.com/search");
          target.searchParams.set("q", command.query);
          await chrome.tabs.update(tab.id, {url: target.href, active: true});
          status = "SUCCEEDED"; detail = `Chrome accepted navigation to ${target.href}`;
        }
      } catch (err) { detail = String(err).slice(0, 1000); }
      const body = {extension_id: chrome.runtime.id, status, detail};
      if (capture !== null) body.capture = capture;
      await chrome.storage.local.set({pendingResult: {id: command.id, body}});
      await request(`/api/bridge/commands/${command.id}/result`, body);
      await chrome.storage.local.remove("pendingResult");
    }
  } catch (err) {
    await chrome.storage.local.set({bridgeStatus: {backend_connected: false, error: String(err), last_seen: new Date().toISOString()}});
  } finally { running = false; }
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "PH_HEARTBEAT" && isTikTok(sender.tab?.url)) {
    tick().then(() => sendResponse({ok: true})); return true;
  }
  if (message?.type === "PH_REFRESH" && !sender.tab && sender.id === chrome.runtime.id) {
    tick().then(() => sendResponse({ok: true})); return true;
  }
});
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === "ph-heartbeat") tick(); });
async function setup() {
  await chrome.alarms.create("ph-heartbeat", {periodInMinutes: 0.5}); tick();
}
chrome.runtime.onInstalled.addListener(setup);
chrome.runtime.onStartup.addListener(setup);
chrome.tabs.onRemoved.addListener(() => tick());
chrome.tabs.onUpdated.addListener((id, change, tab) => { if (isTikTok(tab.url) && (change.status || change.url)) tick(); });
setInterval(tick, 3000);
setup();
