# Target HTTP 403 policy

An exact public video or creator route returning HTTP 403 is persisted in
`blocked_targets` (type, canonical URL, reason, first/last seen, attempt count,
BLOCKED status). Query parameters and fragments are discarded. Blocking survives
worker/backend restarts. Video identity is matched by ID, including renamed creators.
The backend queue and worker guard reject blocked opens/reads with
`TARGET_PREVIOUSLY_BLOCKED`. The existing failed-video list remains a fallback.
There is no automatic unblock, retry, bypass or alternate identity.

A target failure immediately pauses new content operations. A durable worker
outbox and backend `target_security_pending` keep that pause across transport or
worker failures. A subsequent passive heartbeat must observe complete HEALTHY,
CONFIRMED authenticated home/search before classifying TARGET_BLOCK. An older
successful heartbeat is insufficient. No automatic home navigation is performed.
If the user is still on the failed target, operations remain paused until a real
home/search observation becomes available. A healthy target page is insufficient.

Home/search/general-resource HTTP 403, any challenge/captcha/verify-human, or a
degraded session during the home/search verification remains GLOBAL_BLOCK. Three
distinct targets within a rolling ten-minute window trip the global circuit.
Replayed reports are idempotent by canonical URL and observation timestamp.
Ordinary heartbeat processing never clears a global incident. Only an exact
historical target-403 latch may be archived/reclassified after the required fresh
healthy general-page evidence; all incident history and quarantine remain.

`POST /api/bridge/target-403` is used by the registered Companion identity.
`GET /api/bridge/blocked-targets` exposes the local quarantine and pending flag.
Unrecognized individual-resource routes are conservatively treated as global;
the implementation does not guess which general API failures are harmless.

Stage 1 navigates only to search, reads one visible viewport (maximum ten),
persists visible references including blocked video references, and stops. It
never opens result videos. Blocked-reference counts indicate skipped opens, not
dropped observations. A new authenticated operator authorization can arm one
Stage 1 after a new two-sample passive check when no global/pending block exists.
It cannot clear a latch or start Stage 2. Previous attempts remain immutable.

Before the single card read, Stage 1 waits passively for consecutive complete,
HEALTHY/CONFIRMED observations using the shared pacing settings (two healthy
samples, at most eight health samples, within the search timeout). A transitional
UNKNOWN sample cannot authorize capture and no longer fails the command on the
first sample. HTTP 403, challenge or login-required stops immediately. This adds
no navigation retries, card rereads or scrolling. Technical readiness diagnostics
contain only page/session/ready-state labels and sample counts.

An explicitly requested new pilot uses `quarantine_stage1.py --run-id ID` (or the
fixed `background_runner.py quarantine-stage1 --run-id ID` task). Each ID has a
separate durable intent/result artifact; rerunning the same ID is refused.
