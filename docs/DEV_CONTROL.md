# Local development control

## Live authenticated DOM diagnostics (no TikTok reload)

`DEV_INSPECT_TIKTOK_SESSION` uses the existing authenticated maintenance queue to
inspect the already-bound TikTok tab. Its target tab/URL come from the Companion
state and are rechecked before/after reading. It executes only the packaged
`session_probe.js` and stores a bounded technical result in dev_commands.result_json.
It cannot receive arbitrary script, selector, URL or click instructions.

The Companion now has Chrome's `scripting` permission with the existing TikTok host
scope so that a fixed session-only observer can be installed into an already-open
document after a worker update. It installs only session_signals.js and
session_observer.js; no full content reader, collection, page reload or navigation
is involved. PH_SESSION_SIGNALS reads the actual DOM. The observer has one guarded
message listener and no timers. It does not reset the safety latch/collection guard.

DOM-v2 supports current `nav-messages` and `nav-activity` button controls, own nav
profile URLs/avatar, the authenticated navigation context and following-user-button
items. Generic Following text and creator/feed links do not establish account
identity. Profile/avatar are one evidence family; messages/activity another;
authenticated followed-account list is a third. Two families, a healthy complete
page and no strong logged-out CTA are required. Composite sidebar context is not
counted as an additional independent vote.

Positive partial signals are retained even when session confirmation is incomplete.
Selector/count/sample-attribute diagnostics appear only in collapsed technical
details; the mini log contains only semantic transitions. Current document blockers
remain authoritative; a persisted historical security stop is not evidence of
current logout. CONFIRMED + healthy + stop active is valid and the UI action is
waiting_for_collection_recovery. This diagnostic never clears a stop.

## Canonical startup and Companion API contract

`python run.py` now provisions and starts the same owned supervisor backend as
devctl. It no longer silently serves an application with development control
disabled while a provisioned Companion polls its queue. A second direct invocation
prints “Babi já está rodando em http://127.0.0.1:8000” and exits cleanly. A foreign
listener is reported with PID/process when available; it is never terminated.

The canonical maintenance queue remains **GET /api/dev/commands/next**, authenticated
by the existing local token and extension ID. No alias or parallel command API was
added. The router was already registered: the old 404 was the intentional disabled
mode response from `settings()` when PH_DEV_CONTROL was absent in direct startup.
Explicitly disabled/unmanaged ASGI use is not made unauthenticated by this fix.

`config/companion_api.json` defines API version 1 and minimum Companion 0.1.6.
Status and heartbeat responses expose these values and development availability.
Companion heartbeat includes companion_version, build_id and api_version. The build
hash also covers the shared contract. Dashboard displays COMPANION DESATUALIZADO
for version/API incompatibility, independently from transport and session state.
The worker suspends polling/command consumption when negotiation fails; an unexpected
404 is not retried every tick with the same backend contract.

Session controls remain distinct:

- ABRIR TIKTOK uses the existing opener and its safety restrictions.
- RENOVAR SESSÃO queues DEV_RENEW_TIKTOK_SESSION through the same authenticated
  maintenance queue. It reuses the existing browser/tab, or creates one home tab
  inside the running Companion browser. It never clears cookies or security stop.
  Intent is persisted before the single creation/navigation; uncertain outcomes
  are not replayed. A blocked page or new incident stops renewal without retry.
- VERIFICAR SESSÃO invokes the existing passive SAFE_RECOVERY_CHECK. It reads
  Companion evidence and records an audit result; it does not navigate or release.

No session control starts search, discovery, detail, comments or creator collection.

## Explicit session recovery (2026-10-23)

`reload-extension` processes local maintenance even while security is latched,
but never refreshes a page under that latch. Known failed video URLs remain
excluded from default refresh targets even after clearance. Missing/stale worker
heartbeats use the installed Companion's own local bootstrap page only if the
dedicated Chrome profile already has a live process. No second Chrome is opened.
No Chrome preferences, cookies, login or extension registration are modified.

After reconnection, an explicitly requested session recovery uses:

```
.\.venv\Scripts\python.exe scripts/devctl.py validate-home
```

This is a separate authenticated development command, not a content command. It
can navigate one existing TikTok tab to the fixed home URL once, only for the
reviewed historical video HTTP 403. It never navigates to a search or retries a
failed page. It requires two observations of complete, healthy home content and
visible account-specific profile/avatar plus inbox controls. Generic body text
such as Following/Profile/Messages never confirms authentication. Missing evidence
leaves session unconfirmed. Challenge, login or a new security incident fails the
operation. The latch remains active after successful home validation.

Only after inspecting that successful validation, an explicit local operation can
clear that exact incident (use its printed command ID):

```
.\.venv\Scripts\python.exe scripts/devctl.py clear-reviewed-stop --validation-id ID
```

The backend requires fresh (under 15s), authenticated, complete home evidence from
the provisioned extension/build, and an unchanged incident. History and failed URL
are archived before clearing. The worker acknowledges only the matching incident;
a new 403 retains its stop. Neither collector nor runner can clear a latch. No
clearance was performed during the disconnected production validation.

`/api/bridge/state` separates companion_connected, heartbeat_fresh, current_url,
current_page_status, tiktok_session_status, security_stop_active and failed_url.
Stale signals show unknown page/unconfirmed session. Version/build with an old
timestamp describe the last observation, not currently loaded code.

Run from this workspace with the existing environment:

```
.\.venv\Scripts\python.exe scripts/devctl.py status
.\.venv\Scripts\python.exe scripts/devctl.py restart-backend
.\.venv\Scripts\python.exe scripts/devctl.py reload-extension
.\.venv\Scripts\python.exe scripts/devctl.py refresh-tiktok
.\.venv\Scripts\python.exe scripts/devctl.py reload-all
```

`reload-all` drains active operations, gracefully restarts the owned backend,
checks health and run identity, queues DEV_RELOAD_EXTENSION, checks its durable
completion, and waits for a fresh content-script heartbeat with the expected
build. Success prints READY and exits 0. Errors name the failed stage and exit 1.
`--timeout 65` sets each extension completion/reconnection wait (seconds).
No TikTok tab means an explicit failure, not a false connected result.

## Backend ownership

`scripts/dev_supervisor.py` starts only this workspace's absolute `run.py`, using
the current Python interpreter and workspace directory, bound to 127.0.0.1.
`.runtime/backend.pid` is a JSON ownership record containing the launched PID,
OS creation identity, executable, root and random run ID. On Windows the launcher
may have a child interpreter; graceful shutdown happens in the server and both
exit normally. Each readiness check matches the run ID of the owned launch.
Logs append to `.runtime/logs/backend.log`, including launch boundaries.

The supervisor refuses a port occupied by an unmanaged process, refuses a changed
PID identity, and never kills by Python name or listener port. It does not adopt
an existing manual server. A file lock serializes control operations across CLIs.
If graceful exit fails, restart fails without launching a second backend. No
force-kill fallback is implemented.

Maintenance atomically blocks new collection commands/missions while existing
commands can finish. The CLI waits up to 60 seconds for active commands/missions
and development operations. Existing command timeouts still become EXPIRED with
an event; work is never reported as successful just because restart was requested.
Running missions are preserved and prevent restart. Pending mission records stay
unchanged. Maintenance is resumed on CLI exit, has a three-minute crash lease,
and is cleared on backend startup.

## Companion reload and recovery

Development operations use a separate `dev_commands` table and `/api/dev/*`
router. Content command schemas still reject DEV and all engagement commands.
State is PENDING -> ACCEPTED -> SUCCEEDED/FAILED, or EXPIRED after 100 seconds.
Completions require matching ownership and expected build; identical retries are
idempotent. Modified retries are rejected.

The worker stores `pendingDevReload` in chrome.storage.local, acknowledges the
job, then calls chrome.runtime.reload(). A new worker recovers that flag,
selects the pinned HTTPS www.tiktok.com tab (falling back to an existing one),
checks its current URL and reloads only that tab with chrome.tabs.reload. It saves progress and waits for complete content
scripts with the new build. It acknowledges completion before removing the flag.
Transport failures retain progress. A 55-second content-readiness timeout yields
FAILED. DEV_REFRESH_TIKTOK uses the same recovery flow without runtime.reload().
No page clicks, engagement or arbitrary browser scripts are exposed.

The pre-DEV worker needs a one-time bootstrap. If its heartbeat lacks a build ID,
devctl opens `chrome-extension://<pinned-id>/dev_bootstrap.html` in the dedicated
workspace Chrome profile. This is the installed Companion's own local page, not
chrome://extensions and not a web-accessible resource. It loads local config and
build, persists a one-time marker, and invokes runtime.reload() itself. It opens
the existing profile if necessary; it does not terminate Chrome or access personal
Chrome windows. This Windows bootstrap requires Chrome to be installed and the
unpacked Companion already registered in that profile. No extension installation
or security setting changes are automated.

## Local-only security and build identity

The supervisor provisions `.runtime/dev.json` and ignored `extension/dev_config.js`:
a random local token and the already-installed Companion ID from this workspace's
database. Tokens never go into heartbeat, git, page scripts, output or logs.
The config script is imported only in the extension's own contexts. Provisioning
does not request browser permissions or web-accessible resources. The fixed live
session diagnostic separately uses `scripting` with the existing TikTok host scope,
as documented above; it does not expose an arbitrary script execution endpoint.

DEV endpoints are disabled (404) unless PH_DEV_CONTROL=1, set only for supervised
development launches. Enabled endpoints require loopback peer and Host, the local
token, the pinned extension identity for worker operations, and reject foreign
Origin headers. Do not expose the local backend through a proxy/tunnel/network.
Normal `python run.py` keeps development administration disabled.

`extension/build.js` is generated from extension file contents, excluding itself
and local secrets. Heartbeats add optional `companion_version` and a 16-character
SHA-256 `build_id`; legacy seven-field heartbeats still receive 200. The API,
CLI status and panel show the loaded build. A content-script heartbeat also checks
that the new code reached TikTok, rather than assuming worker reload is enough.
Refresh-only cannot load changed worker code: use reload-extension/reload-all.

## Validation on 2026-10-21

Real `reload-all` completed all six stages, refreshed one TikTok tab and returned
READY. The backend was restarted only through its owned run identity. Companion
0.1.5 first confirmed build `b2e7fd11372b9cf2`; a subsequent real self-reload loaded
`ae250948bb887a17` and returned READY again. DEV_REFRESH_TIKTOK also returned READY.
Final automated validation: 88 Python tests and 29 JavaScript tests passed.
Real detail commands #13 through #20
then succeeded sequentially for all eight videos of search capture command:9.
Creator and caption were stored for 8/8. Count elements returned nonnumeric UI
labels (Curtida/Comentários/Compartilhar/Favoritos); numeric values remain null.
This is not evidence that all numeric metrics were extracted. Search coverage and
the library/capture/new/updated counters are independent and preserved.

The first migration attempt using a Chrome process restart did not update the
cached worker and timed out. That fallback was removed from the implementation;
the local Companion bootstrap page solved migration without Computer Use.



## Persistent Chrome and silent local execution

Use `scripts/background_runner.py` for fixed background tasks and
`scripts/devctl.pyw` with the existing pythonw launcher. Logs remain in
`.runtime/logs`. See [Persistent runtime](PERSISTENT_RUNTIME.md).
