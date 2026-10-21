async function refresh() {
  await chrome.runtime.sendMessage({type: "PH_REFRESH"});
  const {bridgeStatus: s = {}} = await chrome.storage.local.get("bridgeStatus");
  document.getElementById("status").textContent = [
    `Extensão: ${chrome.runtime.getManifest().version}`,
    `Backend: ${s.backend_connected ? "conectado" : "desconectado"}`,
    `Chrome: conectado`, `TikTok: ${s.tiktok_open ? "aberto" : "não detectado"}`,
    `Authenticated hint: ${s.authenticated_hint ? "sim" : "não confirmado"}`,
    `Última tentativa: ${s.last_seen || "—"}`
  ].join("\n");
  document.getElementById("error").textContent = s.error || (s.tiktok_open && !s.page_signals?.content_script_connected ? "Recarregue a aba TikTok para ativar o leitor de sinais." : "");
}
document.getElementById("refresh").addEventListener("click", () => refresh().catch(console.error));
refresh().catch(console.error);
