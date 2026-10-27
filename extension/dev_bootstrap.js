/* Initial upgrade of a pre-DEV worker, from its own non-web-accessible page. */
(async () => {
  const status = document.getElementById('status');
  if (!globalThis.PH_DEV || PH_DEV.extension_id !== chrome.runtime.id || !globalThis.PH_BUILD_ID) {
    status.textContent = 'Local DEV configuration missing; no reload performed';
    return;
  }
  const response = await fetch('http://127.0.0.1:8000/api/dev/status', {
    headers:{'X-PH-Dev-Token':PH_DEV.token,'X-Extension-ID':chrome.runtime.id},
    signal:AbortSignal.timeout(5000)
  });
  if (!response.ok) {
    status.textContent = 'Local backend development control is disabled or rejected this Companion';
    return;
  }
  const {devBootstrapBuild} = await chrome.storage.local.get('devBootstrapBuild');
  if (devBootstrapBuild === PH_BUILD_ID) {
    status.textContent = 'This build was already requested. Check devctl status.';
    return;
  }
  await chrome.storage.local.set({devBootstrapBuild:PH_BUILD_ID});
  status.textContent = 'Reloading this Companion extension...';
  chrome.runtime.reload();
})().catch(error => { document.getElementById('status').textContent = String(error); });
