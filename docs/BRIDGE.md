# READ ONLY command bridge — SEARCH sprint

## Activating this update

The running backend uses reload=False. Manually restart it in its existing terminal
when ready, using the same virtual environment and `python run.py`. No environment
recreation or second project copy is needed.

In chrome://extensions reload the unpacked extension from this workspace's extension
directory. If Chrome requests approval of updated permissions (tabs and alarms),
review it yourself. Reload the TikTok tab. The existing .crx is not rebuilt by this
sprint; a packaged installation must be replaced/rebuilt manually.

## Manual acceptance

1. Open the Companion popup: backend, Chrome, TikTok and authenticated hint appear.
2. Open http://127.0.0.1:8000: the diagnostic updates automatically.
3. Enter `home gadgets` in TEST SEARCH and submit once.
4. The existing normal Chrome TikTok tab navigates to
   https://www.tiktok.com/search?q=home+gadgets.
5. Live Log shows PENDING → DISPATCHED → SUCCEEDED. SUCCEEDED means Chrome
   accepted navigation, not that TikTok results loaded or authentication succeeded.
6. Close TikTok only: Companion/Chrome remain connected and TikTok becomes absent;
   SEARCH is disabled. Reopen TikTok to reconnect automatically.
7. Close Chrome: after at most 75 seconds the connection expires. Reopen Chrome
   to recover. With no content script, alarms provide a 30-second fallback;
   an active worker/content script normally sends every 3 seconds.
8. Stop the backend manually if desired: popup displays an error. Restart it and
   refresh popup: recovery is automatic. Never interact with social buttons.

## Protocol and limits

- POST /api/bridge/heartbeat: the single JSON contract is
  `extension_version` (string, default "unknown"), `current_url` (string, default ""),
  `page_title` (string/null, default null), `authenticated_hint` (boolean, default false),
  `page_ready_state` (string/null, default null), `has_search_ui` (boolean, default false),
  `playback_error_visible` (boolean, default false). No cookies, tokens or credentials.
  The existing command-routing extension ID travels in X-Extension-ID, outside
  the heartbeat body. The backend maps these fields to the existing dashboard state.
- POST /api/commands: only {"type":"SEARCH","query":"..."}; 1–200 chars, nonblank.
- GET /api/bridge/commands/next?extension_id=...: atomically claims one pending command.
- POST /api/bridge/commands/{id}/result: only SUCCEEDED or FAILED from claimed owner.
- GET /api/commands: recent command states. Pending/dispatched expire after 45s,
  evaluated on queue access. No automatic replay of dispatched commands.
- Retry of a lost acknowledgement is persisted in extension storage. Repeated
  identical acknowledgement is idempotent. Expired commands cannot finish.
- ID scopes delivery to the reporting extension; it is not an authentication secret.
  This is a local loopback bridge, not an API to expose on a network.
- With multiple TikTok tabs the active one is preferred, then the most recently
  accessed. With multiple Companion profiles, the latest heartbeat owns new commands.
- Authentication remains a text heuristic. No cookie or password inspection.
- No general click API, discovery, AI, extraction, stealth or social actions.

## Validation

`.venv\Scripts\python.exe -m pytest -q` includes a real HTTP test on an ephemeral
port with a temporary SQLite database, without touching the running backend.
`node --test tests/bridge.test.cjs` validates the worker using mocked Chrome APIs;
this does not replace the manual Chrome acceptance above.
