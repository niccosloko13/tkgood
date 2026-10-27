# Safe Collection Recovery v1

This is an explicit manual recovery flow, not a background collector. Browser
engagement, bypass and automatic latch release remain prohibited.

## SAFE_RECOVERY_CHECK

```
.\.venv\Scripts\python.exe scripts/safe_collection.py check
```

The check does not navigate, reload, open tabs, click, scroll or call a TikTok URL.
It consumes existing Companion PH_SIGNALS heartbeats. With a potentially healthy
page, it waits for two distinct fresh heartbeats received after the request, on the
same tab/URL, within 30 seconds. No tab or incomplete evidence returns UNKNOWN.
The four terminal states are HEALTHY, UNKNOWN, BLOCKED and CHALLENGE; PENDING is
only the collection of diagnostic heartbeat samples. Check never releases a latch.

HEALTHY requires the provisioned Companion, matching loaded build, heartbeat under
15 seconds, complete DOM, exact HTTPS www.tiktok.com home/search route, confirmed
session, visible own profile/avatar and account inbox. Following or generic text
is not accepted. Historical latch state is separate from current-page evidence.

An actual page 403/challenge persists an incident and stops work. A missing tab
does not mean the page is healthy or that TikTok globally returned 403 again.

## Explicit release

Only after inspecting a HEALTHY result, the operator can separately run:

```
.\.venv\Scripts\python.exe scripts/safe_collection.py release --validation-id ID --operator-reviewed
```

The authenticated loopback endpoint revalidates fresh healthy evidence, unchanged
incident/tab/URL and absence of active content work. It archives released_at,
validated_url, validation_evidence and previous_incident. History is not removed.
A stale, changed, UNKNOWN or blocked state refuses release. Check, heartbeat,
capture, dashboard reads and background jobs never invoke release.

Release enables a narrow collection guard. General commands/night/enrichment are
not re-enabled. Old pending commands cannot drain under that guard.

## Stage 1

```
.\.venv\Scripts\python.exe scripts/safe_collection.py stage1 --validation-id ID --query "KNOWN QUERY"
```

Exactly one historically observed query, one READ_SEARCH_RESULTS command with
fixed safe options, one search navigation in the validated existing tab if needed,
one bounded card read. At most ten visible anchors/cards, zero scroll, detail,
comments or creator-profile commands. No viewport recapture or transport retry.
Readiness observes tab status/PH_SIGNALS only; UNKNOWN or block refuses card capture.

The updated Companion advertises safe_collection_version=v1. An old build is not
allowed to execute the bounded path. Backend rechecks ownership, limits and latch
before saving. A fresh observed-page heartbeat accompanies the capture completion.
Command readiness is bounded to 35 seconds, within the existing command timeout.

Persistence uses existing save_capture/dedup. Each inserted search observation
calls the central trend snapshot contract in the same transaction. Category
classification is limited to captured IDs; existing identity jobs are enqueued
without running providers. Successful completion is terminal for Stage 1. Failed
attempts are not automatically retried. Repeated result delivery is idempotent.

## Stage 2

Only a successful Stage 1 for the same validation permits an explicit stage2 call.
There is at most one Stage 2 batch per validation: five unique known queries,
30 new videos, 180 seconds wall time, and at most ten results per query or the
remaining new-video budget, whichever is smaller.

```
.\.venv\Scripts\python.exe scripts/safe_collection.py stage2 --validation-id ID --query "QUERY A" --query "QUERY B"
.\.venv\Scripts\python.exe scripts/safe_collection.py next --batch-id ID --operator-reviewed
```

Stage 2 pauses after each capture. Each next query needs another explicit operator
action, fresh healthy state and remaining budget/runtime. There is no automatic
Stage 2 start or loop. The guard continues to reject general collection/enrichment.
Any security incident marks the batch BLOCKED and fails pending content commands.

## Operational status

`scripts/safe_collection.py status` and GET `/api/collection-health` expose Companion,
session, page, security stop, last safe validation/check/collection, new videos and
last stop reason. The existing Core dashboard includes COLLECTION HEALTH. It does
not expose the local development token or auto-release buttons.

Explicit writes are protected by the existing local development authorization,
loopback origin and operator-reviewed release/next payload. Reads do not collect.

## Legacy timestamps

Legacy observations without timezone remain in the library. Their temporal hook
records TREND_SKIPPED_AMBIGUOUS_TIMESTAMP and does not invent UTC or block existing
capture persistence. Normal live observations use actual timezone-aware backend
capture times. Historical fixtures are never mistaken for a production pilot.

## Current production precondition

This sprint found no open TikTok tab. Check is UNKNOWN, stop remains active and no
query was executed. The operator must open a legitimate home/search manually in
the existing Chrome and then request the passive check. Do not open or reload a
page automatically to manufacture HEALTHY evidence.
