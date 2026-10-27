# Connection panel flicker + mini session log

## Result

Connection panel updated without full-container replacement. Real-browser audit
passed for **60.047 seconds**, against the running local backend: **20 polls**, one
request in flight at most, stable buttons, focus and scroll, no repeated log entries.
No TikTok navigation, session renewal or collection was executed in this sprint.
Security stop and incident history remain exactly unchanged. No commit.

## Cause

The previous `refresh()` did not replace the whole Conexão section, but it repeatedly
rebuilt its descendants and wrote conflicting presentations of the same state:

1. Initial `uiStatus(bridge)` recreated `quickStatus` and `connectionFacts` with
   innerHTML and wrote session/browser/diagnostics.
2. The same poll rewrote sessionStatus with another innerHTML representation,
   rewrote diagnostic messages and appended heartbeat/version text.
3. After unrelated library/candidate/quality/log requests, `uiStatus(bridge)` ran
   again, reverting those fields. This produced visible intermediate states even
   when the actual session had not changed.

The 3s `setInterval` did not wait for async refresh completion. Renew/verify/open
also scheduled additional refresh timeouts, allowing overlap and resetting action
feedback. The buttons themselves were originally static; they remain static.
The category script's separate 10s check is unrelated to connection polling and
was not repurposed or expanded.

## Implementation

- Removed the repeated session/diagnostic repaint paths. Connection fields are
  mounted once and updated through equality checks on individual text/disabled
  values. `connectionFacts.innerHTML` is not used by the new connection renderer.
- One owned 3s timeout chain waits for refresh completion. Section changes cancel
  and replace the previous timer; pagehide stops it. Restarting polling repeatedly
  never accumulates timers. Connection requests share a single-flight promise.
- While Conexão is selected, polling reads only **GET /api/session/state**. It does
  not run page-wide library/quality/candidate rendering. The endpoint is a read-only
  projection of existing bridge, renewal and verification records.
- Buttons retain their original DOM nodes and event bindings. No poll replaces
  action containers, moves focus, resets scroll or recreates controls.
- Renewal keeps `renewing` until its existing job finishes, then waiting_for_login,
  ready_to_verify or an explicit blocked/error result. Intermediate polls do not
  erase the action message. Renewal/check no longer add refresh timers.
- Verify logs one “Verificando sessão...” line per action, then the result; it uses
  the existing passive check and never navigates or releases a stop.

## Mini log and evidence

ÚLTIMOS EVENTOS retains at most **10 lines**, with green OK, yellow warning, red
blocked/error and gray info. It logs semantic transitions only: Companion,
heartbeat recent/stale, tab, URL, page, session evidence, session and stop.
Changing only last_seen updates its field without adding a log line.

The log has fixed height; appending events does not grow the page. It does not
force-scroll the user. Repeated identical API failures are deduplicated by endpoint
and status; recovery is logged once. Errors show the failing `/api/...` URL and
HTTP status, including `/api/dev/commands/next [404]` if reported by the Companion.

Profile/Avatar are derived only from the existing compound
visible_own_profile_with_avatar evidence; Messages from visible_account_inbox.
Activity remains **não observado** because the Companion does not supply it; it is
not invented or made a new login requirement. Missing required evidence is listed.
Logged-out detection is separated from absence of data. Unknown/stale evidence is
not shown as authenticated proof.

## Real 60-second audit

Executed `scripts/validate_connection_panel.py` with an isolated headless test
profile, against localhost only. It did not attach to the authenticated Chrome,
load its profile/extensions, or navigate TikTok/CDN. Network interception permitted
only loopback GET requests. No off-origin requests were attempted by the page.

Authoritative result: `browser-60s.json`.

- Duration: **60.047s**; 13 samples across the observation window.
- Connection polls: **20**; maximum concurrent session requests: **1**.
- Active connection polling timers: never more than **1**.
- Mini log: **8 lines** throughout the window, unchanged; no poll spam.
- Heartbeat timestamp advanced while session values remained stable.
- All four original button nodes remained connected, enabled and identical.
- Focus remained on `verifySession`; window scroll remained unchanged.
- No element removals/replacements in the observed connection section.
- Zero JavaScript exceptions.
- Before/after screenshots inspected. Pixel differences were confined to heartbeat
  digits, bounding box **(1077, 605)–(1151, 615)**. Button/card layout did not change.

The initial audit driver was corrected to continuously process its network
interception events while observing; its original waiting loop artificially paused
requests. The final successful run above uses the corrected driver. No application
threshold was lowered to make it pass.

## Command API and session state

The Companion now reports the actual maintenance-queue HTTP status/error in its
existing heartbeat. These are optional diagnostic fields, without changes to
collection commands, session evidence rules or security behavior.

At final verification:

- `/api/dev/commands/next`: actual Companion status **200**.
- Current owned backend log segment: **136 queue 200s, zero queue 404s**.
- Companion connected; heartbeat recent; TikTok tab detected.
- Current session: **unconfirmed**, displayed as **Unknown**.
- Current page: **unknown**; no account evidence was fabricated.
- Security stop: **active**, unchanged from the checkpoint.

The worker was reloaded through Dev Control to expose diagnostic metadata, under
the active latch: **zero TikTok tabs refreshed**. No renew/open/check action was
executed on the authenticated browser during the UI audit.

## Preservation

72 existing tables compared with `checkpoint.db`; **69 identical**. Expected
operational changes are events, system_state/heartbeat and dev_commands for local
maintenance. Original event rows remain present. Exact security-stop and history
rows are unchanged.

Collection commands, search observations, trend snapshots, Gold, candidates,
identity decisions/entities, category/evidence and all business records remain
unchanged. This sprint did not modify collection, trend or identity algorithms.

## Tests

- **466 Python passed**, seven existing deprecation warnings; task
  `ff3ba79628c248fe831eb7138f9869f5`.
- **141 Node/dashboard passed**, zero failures/skips; task
  `e0eacba9388047f0acd520d052727e53`.
- Six new Node cases: single timer, unchanged-state zero mutations, stable controls,
  heartbeat/session transitions, no log spam, max log size, single-flight polling,
  verify/renew behavior and visible command 404/recovery.
- Two new Python cases: lightweight read-only state endpoint and real heartbeat
  diagnostic status propagation, without content commands or checks being created.
- Existing fixture compatibility retained; event listeners are guarded for minimal
  DOM test environments. No tests or assertions were removed.

## Files

`app/static/index.html`: connection renderer, log, controls and polling lifecycle.
`app/session_api.py`: small read-only session state projection.
`app/schemas.py`, `extension/dev_worker.js`, `extension/background.js`: optional
command API diagnostics in the existing heartbeat.
`tests/connection-panel.test.cjs`, `tests/test_session_panel.py`,
`scripts/validate_connection_panel.py` and artifacts in this folder.

## Manual action

Refresh only the dashboard page to load the new UI. No TikTok reload, login change
or security-stop release is required for this UI fix.
