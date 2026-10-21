# READ ONLY command bridge — SEARCH and visible Search Capture

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
8. After SEARCH finishes and results appear, click CAPTURE RESULTS. Verify that
   VIDEOS increases and RECENT VIDEOS shows creator/caption/views/query/time and OPEN.
9. Click CAPTURE RESULTS again on the same viewport: count must not increase;
   first_seen_at remains unchanged and last_seen_at advances. OPEN only opens a new tab.
10. Live Log must show Capture requested → Reading visible search results →
    N result links detected → N unique observations stored → N duplicates updated
    → Capture completed. Zero visible links is reported as zero, without invented data.
11. Stop the backend manually if desired: popup displays an error. Restart it and
   refresh popup: recovery is automatic. Never interact with social buttons.

## Protocol and limits

- POST /api/bridge/heartbeat: the single JSON contract is
  `extension_version` (string, default "unknown"), `current_url` (string, default ""),
  `page_title` (string/null, default null), `authenticated_hint` (boolean, default false),
  `page_ready_state` (string/null, default null), `has_search_ui` (boolean, default false),
  `playback_error_visible` (boolean, default false). No cookies, tokens or credentials.
  The existing command-routing extension ID travels in X-Extension-ID, outside
  the heartbeat body. The backend maps these fields to the existing dashboard state.
- POST /api/commands: {"type":"SEARCH","query":"..."} (1–200 chars, nonblank), or
  {"type":"READ_SEARCH_RESULTS"}. Capture query is taken from the current bridge
  search URL. Both schemas forbid extra fields; all other command types are rejected.
- GET /api/bridge/commands/next?extension_id=...: atomically claims one pending command.
- POST /api/bridge/commands/{id}/result: only SUCCEEDED or FAILED from claimed owner.
  A successful READ_SEARCH_RESULTS includes `capture` with query, page_url,
  results_count, links_detected, results. Query must match the queued command and
  the search URL. Results must contain unique valid TikTok video URLs, at most 100.
  Capture data is forbidden on SEARCH and failed acknowledgements.
- GET /api/videos/count: {total}, global unique video count.
- GET /api/videos/recent: {total,items}, latest 20 observations ordered by last_seen_at.
- GET /api/commands: recent command states. Pending/dispatched expire after 45s,
  evaluated on queue access. No automatic replay of dispatched commands.
- Retry of a lost acknowledgement is persisted in extension storage. Repeated
  identical acknowledgement is idempotent. Expired commands cannot finish.
- ID scopes delivery to the reporting extension; it is not an authentication secret.
  This is a local loopback bridge, not an API to expose on a network.
- With multiple TikTok tabs the active one is preferred, then the most recently
  accessed. With multiple Companion profiles, the latest heartbeat owns new commands.
- Authentication remains a text heuristic. No cookie or password inspection.
- READ_SEARCH_RESULTS sends one semantic message to the existing TikTok content
  script. `extractSearchResults()` only reads currently rendered viewport cards,
  using video anchors, stable data-e2e attributes and a bounded ancestor fallback.
  No minified CSS classes are required. No scrolling, clicking, TikTok API calls,
  comment expansion, discovery, AI, stealth or social actions.

## Storage and deduplication

Startup safely migrates the existing SEARCH-only queue constraint, preserving
commands. SQLite stores one `video_observations` row per canonical HTTPS TikTok
video URL; query/fragment tracking is removed. Source is always tiktok.
Each row includes search_query, visible creator/caption/metrics/raw text,
extraction_version, collected_at, first_seen_at and last_seen_at. Timestamps are
UTC server receipt times. collected_at and last_seen_at update on recapture;
first_seen_at and id stay unchanged. search_query identifies the latest capture.
The latest visible snapshot replaces prior values, including null when a field is
no longer visible. Abbreviated metric text is preserved, without numeric inference.

Observations, completion state and capture log entries commit in one transaction.
A persisted result hash makes a retry idempotent; a modified acknowledgement of
an already completed command is rejected. Failed/expired/unclaimed commands
cannot add observations. Result counts, query provenance and URLs are validated
by strict Pydantic schemas. No schema or database change is made to the heartbeat.

## Validation

`.venv\Scripts\python.exe -m pytest -q` includes a real HTTP test on an ephemeral
port with a temporary SQLite database, without touching the running backend.
`npm ci` installs the test-only HTML parser. `node --test tests/*.test.cjs`
validates SEARCH, extraction from tests/fixtures/tiktok-search.html, hidden/offscreen
nodes, invalid links, null fields, deduplication and dashboard rendering. The HTML
parser uses explicit fixture geometry because it has no browser layout engine.
Python integration tests run the actual content script, extractor and background
against the temporary HTTP API and SQLite, including repeated capture and logs.
These tests do not replace manual acceptance in the authenticated normal Chrome.

Live capture verified on 2026-10-21 through the running local API: capture #3
inserted 8 unique videos; capture #4 inserted 0 and updated the same 8. IDs and
first_seen_at were preserved and last_seen_at advanced. Live Log contained the
full requested sequence. Dashboard visual confirmation remains a manual check.
