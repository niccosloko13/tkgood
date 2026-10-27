# Persistent Chrome and silent execution

Local backend, supervisor, task workers and subprocess tests still use
`scripts/process_runtime.py` (`CREATE_NO_WINDOW`, hidden STARTUPINFO, redirected
stdin/stdout/stderr). `scripts/devctl.pyw` delegates to the fixed
`scripts/background_runner.py`. No arbitrary shell task is accepted. Task JSON
and logs remain in `.runtime/logs`; submission alone is never success.

The retired runtime policy, endpoints, CLI switches, configuration file, dashboard
controls and paused-command status have been removed. Legacy paused database
commands become FAILED without replay; IDs, query, details and collected evidence
are preserved. The legacy status string remains only in migration compatibility.

## Browser lifecycle

`POST /api/tiktok/open` inventories only the workspace's exact dedicated Chrome
profile. A live process is reused. Failed inventory refuses a duplicate launch.
Opening Chrome happens only when that profile has no live process. Chrome remains
open across commands and backend/Companion reloads. No process termination is used.

The Companion pins `tiktokTabId` in local extension storage. It prefers that tab
even when another TikTok tab is active. If it is gone, an existing TikTok tab is
selected. A new tab is created only for an explicit open request when no TikTok
tab exists. Content commands navigate that same tab; profile reading returns to
the originating video if the user has not changed the route. No focus/visibility
spoofing or visibility-based retry occurs. Each explicit command may restore the
same window once if its real Chrome state is minimized, and select its existing
inactive tab. It never repeats activation based on document visibility.
Explicit development reloads refresh only the selected TikTok tab, preserving IDs.

## Readiness and pacing

Shared timing is in `extension/pacing.js`: 1-second samples, 2 stable samples,
2.5-second command/navigation cooldown, 25-second reader readiness budget,
3 transport attempts, 8 bounded discovery stability samples. Video/profile identity
and real metadata readiness remain required; numeric placeholders never become
invented counts. Search waits for nonempty stable result identities/captions.
Discovery additionally waits for stable viewport data and preserves its original
5-scroll/30-video/90-second limits and exact-retry cache.

Document visibility is diagnostic only. CSS/geometry checks still exclude hidden
or offscreen elements; removing the global policy does not invent rendered data.
Background Chrome may throttle timers or defer page data. A readiness timeout is
reported, without refresh/relaunch loops.

## Security stop

`extension/safety.js` checks DOM evidence before semantic reads and during bounded
scrolling. Companion `webRequest.onCompleted` observes actual TikTok main-document
and XMLHttpRequest HTTP 403 responses. Access Denied, CAPTCHA and security challenge
set durable extension `securityStop` and backend `browser_security_stop` records.
Pending/running browser commands fail, discovery records `security_challenge`, and
future collection/open requests are refused. Backend status exposes the reason;
events and backend/task logs preserve it. Local product detection remains usable.

There is no automated clearing, refresh fallback, user-agent change or challenge
bypass. After human review, recovery is an explicit local operator action; do not
delete a latch merely to finish validation. No external commercial links are opened.

## Commands

```powershell
.\.venv\Scripts\python.exe scripts/background_runner.py devctl status
.\.venv\Scripts\python.exe scripts/background_runner.py devctl reload-all
.\.venv\Scripts\python.exe scripts/background_runner.py pytest
.\.venv\Scripts\python.exe scripts/background_runner.py node-tests
.\.venv\Scripts\pythonw.exe scripts/devctl.pyw status
```

Real sprint outcomes and outstanding limitations are recorded in
[NEXT_SESSION.md](NEXT_SESSION.md) and `data/persistent_runtime_validation.json`.
