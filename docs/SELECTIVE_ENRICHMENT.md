# Selective enrichment v1

This is a scheduling policy, not an opportunity score, final ranking or market
prediction. The current scope is the latest completed Stage 2 batch. Older local
observations can supply supporting facts, but no new browser observations are
used to choose the pilot. Selection freezes each selected video's features,
reasons and intelligence before any reader starts.

## Priority policy

HIGH requires a literal specific product phrase recognized by the existing
deterministic vocabulary/specificity policy, an observed creator and caption,
and at least one supporting fact: Home classification, multiple queries, local
first-seen within 48 hours, existing purchase-intent comments, at least 10,000
historically visible views, available engagement metrics, known candidate creator
coverage or local temporal coverage. High repeat density with one query, no
novelty and no purchase intent reduces priority. Medium retains specific or
category/query-supported items for later. Low lacks sufficient product support
or is quarantined. Insufficient means caption/observed creator or specific context
is missing. Quarantine always excludes selection.

Features record novelty, capture recurrence, query diversity, known candidate
video/creator coverage, historical nonnull visible metrics, purchase intent,
category relevance, specificity, lifecycle/temporal readiness and duplicate
density. Missing metrics remain null. Recaptures and unconfirmed candidate peers
are explicitly not independent same-product or market-trend proof. A closed
vocabulary can miss an apparently specific caption; this version does not expand
detection, infer an invisible product, or promote Medium merely to fill a quota.

Scheduling prefers buckets, then query diversity, novelty, and stable video ID.
No numeric final opportunity score is computed. Only up to five HIGH items are
selected, respecting the existing maximum-five batch authorization; fewer are
processed when fewer qualify. The first real preview contained four HIGH items.

## Execution and safety

`selective_runs` and `selective_items` persist frozen priority, before/after state,
current step, observation/command IDs, reuse reasons and terminal outcomes. A
unique pilot key refuses accidental relaunch; a partial index admits only one
running pilot. The fixed `selective-enrichment` background task has a 600-second
active deadline. It will not admit another step without its conservative command
budget. Development control sees the run as a live operation and cannot restart
the backend during it. Restart recovery marks it interrupted, without replay.

For each selected video the order is detail, comments, creator. Before each step,
saved data is reconciled. Detail/comment data under 24 hours and existing creator
observations under the configured 168-hour window are reused. Comments use the
existing semantic sampler, target 30 and hard maximum 100; only its dedicated
comments container may scroll. No feed scroll, replies, likes, composer, other
engagement, external-link navigation, visual work or supplier work is added.
Caption hashtags are projected from the actually visible saved caption and retain
the detail-observation ID and extraction method. The original metric evidence and
real observation timestamps remain attached to every collection.

The existing search-only guard is not disabled. A temporary permit admits only
the frozen selected ID and current reader step, with an observed creator URL and
bound return video. Unrelated/search commands are refused while the pilot owns
the tab. Both queue and Companion consult target quarantine. A quarantined URL is
skipped without opening/revalidating it. Target 403 is quarantined; continuation
requires passive healthy general-page evidence. If that evidence is unavailable,
the pilot stops with TARGET_HEALTH_PENDING rather than navigating to manufacture
it. Challenge, confirmed logged-out state, global latch or degraded session stops
further browser work. Fixed semantic safety guards check confirmed logout during
comment sampling as well. There is no automatic retry of a failed reader.

## Intelligence and UI

Only videos with collected evidence receive `intelligence_core.identify` in its
existing local, non-embedding path, then existing purchase-intent, signal-quality,
product-quality, creative, trend and commercial dimension analysis/persistence.
There is no global queue drain, clustering, new AI provider, OpenCLIP/FAISS work,
global detector recalibration or final opportunity score. Identity/readiness may
remain unresolved or insufficient when the extra data does not support a stronger
claim. Creator signal reports observed count coverage; follower count is not an
independence or quality conclusion. Local recomputation can complete after a
security stop for already collected evidence, without another browser request.

An audit hashes unselected intelligence and reader-observation rows before/after.
Shared creator observations are intentionally reusable across videos; creator
linking performed by the pilot is scoped to the selected video. Before/after
reasons and evidence IDs remain available even when a dimension is unchanged.

TOP CANDIDATES is on the Collection dashboard and Intelligence Core page. It shows
video, bucket, why, current intelligence, frozen before/after states and enrichment
status. Loading/refreshing it is read-only and never starts a pilot. Its fixed
manual start/stop controls use same-origin endpoints. API:

- GET `/api/selective-enrichment`
- POST `/api/selective-enrichment/start`
- POST `/api/selective-enrichment/{id}/stop`

The real pilot report is `artifacts/selective-enrichment/pilot-v1.json`; lifecycle
and stdout are `.runtime/logs/task-ID.json` and `.runtime/logs/task-ID.log`.

## One next HIGH after manual CAPTCHA intervention

`manual-captcha-resume` is a separate fixed task, explicitly authorized by the
operator. It does not solve CAPTCHA or navigate to manufacture a recovery. It
requests the existing passive two-heartbeat check, then calls a separate
authenticated explicit release endpoint only when its evidence is still fresh,
HEALTHY/CONFIRMED, bound to the same incident/tab/URL/Companion build, with no
target-health hold or active operation. A changed/new incident rejects release.
The old CAPTCHA event and the exact validation samples are appended to history;
the worker clears only the matching old local latch through its existing
clearance handshake. Neither heartbeat nor check alone releases anything.

The original first target is stored in `temporary_target_quarantines` with
TEMPORARILY_QUARANTINED / CHALLENGE_TRIGGER_CONTEXT. It is associated with the
moment of challenge, not asserted to be its technical cause. This does not create
an HTTP-403 event or count toward the 403 circuit. The combined blocked-target
registry and worker/maintenance guards refuse it, including renamed-video URLs.
No automatic expiry/reopen is provided; a later explicit human review is needed.

Only the next SELECTED HIGH in the original frozen order gets a child permit.
The permit contains exactly one ID and a maximum 300-second runtime. Repeated
release/next requests return the same stored outcome/child; the fixed task also
has an exclusive intent and never reruns a child. Remaining candidates are not
processed. The interrupted parent, original priority and old data remain intact.

The child pre-check and each post-check consume two distinct new authenticated
heartbeats after creation/command completion. Loading/unconfirmed samples wait
within 25 seconds; no old pre-navigation heartbeat can authorize the next stage.
Post-profile health must describe the bound return video. 403, CAPTCHA/challenge,
verify-human/confirmed logout or a security latch stops immediately. Individual
target 403 keeps the existing quarantine classification and does not automatically
become global. A saved recent observation can be reused instead of a browser
request; it is explicitly marked REUSED/NO_BROWSER_ACTION.

Artifacts: `artifacts/selective-enrichment/manual-captcha-resume-v1.json`, the
matching fixed background task's lifecycle/stdout, and the immutable recovery
record linking the parent, temporary context, passive check and one child run.
