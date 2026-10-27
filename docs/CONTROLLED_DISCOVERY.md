# Controlled Discovery Expansion

`DISCOVER_MORE_RESULTS` is a dedicated semantic command for the current public
TikTok search page and one explicitly chosen query. It cannot scroll a feed,
profile, video or changed search query, open a video, click a page control or
perform engagement. Existing APIs/readers remain separate.

## Limits and lifecycle

Limits are 5 scrolls, 30 new Library videos, 30 unique session videos (an additional
conservative ceiling) and 90 seconds of execution. Viewport 0 is captured before
the first scroll. The content script waits for stable result identities/text after
every scroll. Document visibility is diagnostic only. Real CAPTCHA/login/security
elements and HTTP 403/Access Denied stop browser operations persistently.
The scroll target is the nearest visible, vertically scrollable ancestor containing
at least two canonical result identities, outside navigation/dialog/sidebar/feed
contexts, on the verified search route. A scrollable search document is the fallback.
The backend retains target type and actual scrollTop before/after for audit.

Two cycles without new IDs stop discovery. Two cycles without DOM card-count growth
also stop it, even if a virtualized viewport rotates IDs; `stop_detail` distinguishes
`no_new_ids` from `dom_not_growing`. This can intentionally stop early on virtualized
results. Bounds are checked by the backend and content script. Configuration is in
`config/discovery.json`; tests check agreement with Companion hard safety caps.

Session states: PENDING / RUNNING, then FINISHED, CANCELLED or FAILED.
STOP DISCOVERY terminates pending or dispatched commands locally; a late viewport
cannot reopen them. The original execution deadline is preserved.
Budget expiration is observed at the next control check, so bookkeeping/transport
can finish slightly after the deadline; no further scroll is allowed.

The Companion stores its active command and exact pending viewport in local storage.
The content script caches at most six bounded viewport responses and a per-document
nonce. A retry cannot scroll the same iteration again. A replaced document cannot
resume an uncertain scroll sequence. Backend step hashes reject modified retries.
Each viewport is persisted atomically rather than waiting for a final 90-second blob.

## Persistence and appearances

`discovery_sessions`, `discovery_steps` and `discovery_session_videos` record query,
limits, progress, stop reason, timestamps, results/unique/new counts, duplicates and
per-viewport new IDs, duplicate IDs and DOM card counts.

Each viewport is a normal search capture with a stable ID
`discovery:<session>:<iteration>`. Existing canonical video identity deduplicates the
Library; the same video can retain appearances under multiple queries and depths.
Search observations add `visible_position`, nullable `global_position_estimate`
and `scroll_iteration`. Global position remains null: virtualized DOM does not prove
ranking. Existing search_position remains viewport-relative. Video rows add
`first_search_query` and `latest_search_query`, with historical backfill from actual
stored appearances. first_seen is preserved; last_seen updates through the approved
repository. No raw DOM snapshots are stored for expanded discovery. Visible text
is capped at 2,000 characters per card, 30 cards per viewport, six viewports.

`duplicates` counts repeated result occurrences between session viewports; it is
not the number of pre-existing Library videos. `new_videos` is actual insertion
into the Library. New session IDs and existing Library IDs are distinct concepts.

## Enrichment and product detection

New videos enter `video_enrichment_queue` with needs_detail, needs_comments,
needs_creator, needs_product_detection and uniform priority. Queue reads reconcile
flags against actual persisted observations and detection/vocabulary versions.
Nothing automatically enriches the whole corpus.

Fixed background tasks:

```
.\.venv\Scripts\python.exe scripts/background_runner.py discovery-session --query "home gadgets"
.\.venv\Scripts\python.exe scripts/background_runner.py discovery-session --enrich-session SESSION_ID --limit 3
```

The second task selects only new videos in that session, at most 10 (default 3),
and sequentially requests the existing detail, 30-comment sample and observed
creator profile readers. Failures, waiting or security conditions stop the batch.
It then runs local product detection/corroboration over persisted data. It neither
generates more queries nor follows external links. There is no scoring/threshold
change, clustering, brand/price resolver, OCR, visual recognition or AI.

## Local vocabulary review

The existing unresolved-phrase area now offers Approve/Reject. Approval activates
an exact conservative phrase in SQLite-backed local vocabulary configuration;
revision changes from product-vocabulary-v1 to v2, etc. An identical retry does
not increment it. Rejecting an active term deactivates it and creates a new revision.
Pending/rejected suggestions never enter extraction automatically.

Approval itself creates no candidate and performs no detection or TikTok command.
A new detection run is required. Runs store vocabulary_version both as a column
and in the configuration/report. Old evidence and candidates are not erased by a
later vocabulary rejection. The historical vacuum cleaner suggestions are not
approved by this sprint's validation.

## UI and API

Collection has a compact Discovery Depth card with start/progress/stop; it shares
the existing three-second dashboard refresh. No new page, polling loop or redesign.
Labels and local phrase review support PT-BR and ar-EG/RTL.

- POST `/api/commands`: typed DISCOVER_MORE_RESULTS with query and optional lower limits.
- GET `/api/discovery/sessions`
- POST `/api/discovery/sessions/{id}/stop`
- GET `/api/discovery/enrichment-queue?session_id=...`
- GET `/api/videos/{platform_video_id}/search-appearances` (latest 100, total retained)
- Companion-only ownership-bound control/step/finish under `/api/bridge/discovery/{command_id}`.

Current real validation, sample outcomes and limitations are recorded in
`data/persistent_runtime_validation.json` and [NEXT_SESSION.md](NEXT_SESSION.md).


Current runtime and validation: [PERSISTENT_RUNTIME.md](PERSISTENT_RUNTIME.md).
