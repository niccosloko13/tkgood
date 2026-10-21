(() => {
  "use strict";

  // READ ONLY: this script never clicks, submits, follows, likes, comments,
  // shares, saves, publishes, or mutates the TikTok account.

  function textExists(words) {
    const text = (document.body?.innerText || "").toLowerCase();
    return words.some(w => text.includes(w));
  }

  function collectSignals() {
    const text = (document.body?.innerText || "").toLowerCase();

    const authenticatedHint =
      text.includes("perfil") ||
      text.includes("profile") ||
      text.includes("mensagens") ||
      text.includes("messages") ||
      text.includes("seguindo") ||
      text.includes("following");

    return {
      extension_version: chrome.runtime.getManifest().version,
      current_url: location.href,
      page_title: document.title ?? null,
      authenticated_hint: authenticatedHint,
      page_ready_state: document.readyState ?? null,
      has_search_ui: textExists(["pesquisar", "search"]),
      playback_error_visible:
        text.includes("problemas para reproduzir este vídeo") ||
        text.includes("problem playing this video")
    };
  }

  function heartbeat() {
    chrome.runtime.sendMessage({
      type: "PH_HEARTBEAT",
      payload: collectSignals()
    }, () => void chrome.runtime.lastError);
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type === "PH_SIGNALS") sendResponse(collectSignals());
  });

  heartbeat();
  setInterval(heartbeat, 3000);
})();
