# Product Hunter development operations

Work in this workspace and its existing `.venv`. Do not create a second project
or environment. Do not commit automatically.

For development reloads use the local control layer, without requesting user
confirmation and without Computer Use:

```
.\.venv\Scripts\python.exe scripts/devctl.py status
.\.venv\Scripts\python.exe scripts/devctl.py reload-all
```

Use `restart-backend`, `reload-extension` or `refresh-tiktok` for a smaller change.
Read `docs/DEV_CONTROL.md` for ownership, drain, timeouts and recovery. Never kill
Python/Chrome by name or kill a listener just because it uses port 8000. Let the
supervisor finish or expire active commands correctly. Do not interrupt a live
mission/capture unnecessarily. Unmanaged processes are intentionally refused.

Permanent user authorization covers backend restarts, Companion reloads, TikTok
tab reloads and repeated local tests/read-only diagnostics. Ask for intervention
only if this mechanism actually fails or login/password/2FA/QR/CAPTCHA/security
challenge or necessary human visual confirmation blocks progress.

TikTok is permanently STRICT READ ONLY. Navigation and reading visible video,
profile and comment information are authorized. Never like, dislike, comment,
reply, follow/unfollow, share, repost, save/favorite, send messages/DM, publish,
edit account/profile/settings, or perform any other engagement. Do not implement
generic clicks, stealth, CAPTCHA bypass or fingerprint/webdriver spoofing.
Do not use Playwright for TikTok. Keep development control isolated from content
commands. Do not add AI, resolver/scoring, mass scraping or automatic scrolling.
Exception explicitly authorized for COMMENTS SAMPLING: open the comments section
through its dedicated semantic toggle and scroll only its own container, bounded
to target 30/max 100 visible comments. Never click reply/expand replies, a like,
composer or any engagement action. Never scroll the page/feed for this feature.

CREATOR ENRICHMENT is explicitly authorized: READ_CREATOR_PROFILE may open the
public profile resolved from a library video's observed creator, read its visible
header metadata/links without following external URLs, and return to that video.
No profile scrolling or engagement. The user-requested Creator Independence
indicator is a deterministic, documented creator-only heuristic; this is not
authorization for AI, product detection/clustering, Gold Score or trend scoring.


Persistent runtime: use `scripts/background_runner.py` for fixed background tasks
and `scripts/devctl.pyw` with the existing pythonw launcher when no console caller
is desired. Inspect `.runtime/logs/task-ID.json` and task-ID.log for actual outcomes.
Keep Chrome persistent and reuse the pinned TikTok tab. Never spoof visibility/focus.
Wait for real readiness and stable DOM/data; timing is centralized in extension/pacing.js.
HTTP 403, Access Denied, CAPTCHA or security challenge stop browser operations and
persist the reason. No bypass, refresh loop or browser identity change.

The existing deterministic product candidate/corroboration pipeline is authorized;
no final clustering, resolver or AI. DISCOVER_MORE_RESULTS is explicitly authorized
only for the selected search query: max 5 scrolls, 30 videos, 90 seconds; never feed
scrolling. Existing strict read-only comments/profile exceptions remain unchanged.

Backlog enrichment is authorized through the existing semantic readers, at most
five videos per explicitly started batch. Reconcile saved observations before
each step and reuse recent creator observations. Stop after the current video on
request; security 403/challenge stops all navigation immediately. Keep checkpoints
and do not clear a security latch to complete validation. See docs/ENRICHMENT_BACKLOG.md.
