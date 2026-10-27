# Enrichment backlog

The existing Library is processed through the existing semantic commands only.
No discovery, generic clicks, TikTok engagement, external-link navigation or product
resolver is added by this orchestrator.

`config/enrichment.json` centralizes batch size (5), comment target (30), creator
reuse window (168 hours), polling (2 seconds), command timeout (105 seconds), and
diagnostic generic heads. Product weights, thresholds and vocabulary are untouched.

## Persistent state

`enrichment_stages` stores video/step, pending/running/complete/failed/not_applicable,
command ID, observation ID, reason and timestamp. `enrichment_batches` stores the
selected IDs, progress, stop flag, terminal outcome and checkpoint JSON. An SQLite
unique partial index permits only one running batch. No browser mission is started
in a request handler; a single background thread runs the selected five videos.

Readers still execute in the Companion on the persistent pinned TikTok tab with
the existing pacing. Product detection runs after the available reader stages for
each selected video; the existing detector atomically recalibrates corroboration
and relationships. Local detection does not fetch anything.

Selection is deterministic and lexicographic: discovery-origin videos, useful
caption (at least 12 characters), candidate/unresolved evidence, unknown creator;
ties prefer recent first_seen_at, then ID. The API exposes priority components and
numeric enrichment_priority; these are scheduling diagnostics, never identity scores.

Before each step, persisted observations are reconciled again. Detail requires
caption or creator metadata; comments reuse a persisted bounded sample with visible
rows or a terminal no_more_loaded observation. Recent profile observations are
shared through video_creators, so the same creator is not opened for each video.
Complete means available data was read, not that every field contains a value.

A confirmed FAILED/EXPIRED command is isolated to that stage; the other videos
continue. Comments become not_applicable when valid detail is unavailable. Unknown
transport outcomes stop the batch to avoid overlapping/repeating a possibly live
command. Any security latch stops all further navigation. No automatic retries of
failed stages occur; explicit `retry_failed:true` is required.

Stop requests finish the current video, including its persisted observations and
local detection, then leave the remaining videos pending. On backend startup a
running batch becomes interrupted; running stages become failed, then observations
are reconciled. A later explicit batch will not repeat valid saved work. DEV CONTROL
includes the active batch in its drain guard; never kill/restart a live batch.

## API and dashboard

- GET `/api/enrichment`: per-video stages, priority, coverage, counts, batch history.
- POST `/api/enrichment/batches`, body `{}`: next at most five pending videos.
- Same endpoint with `{"retry_failed":true}`: explicit failed-stage retry.
- POST `/api/enrichment/batches/{id}/stop`: stop after the current video.

The Coleta card uses the existing dashboard refresh and PT-BR/ar-EG labels. It
has start/stop controls, current video/step, and expandable per-video states. It
does not create a page or invasive modal. Other content commands are refused while
the batch owns the tab. Read-only status, local reviews and dashboard remain usable.

## Broad concept diagnosis

`product_candidates.broad_concept` flags names consisting solely of configured
generic heads. It does not change scores/status or merge anything. See
[ESCOVA_REVIEW.md](ESCOVA_REVIEW.md) and `data/escova_before_backlog.json` for the
original two-video/two-creator hypothesis and the distinction from physical identity.

Real batch results and final coverage: `data/backlog_validation.json` and
[NEXT_SESSION.md](NEXT_SESSION.md). Backup: `data/product_hunter.pre_backlog.db`.
