# Trend History + Velocity Engine v1

`app/trend_history.py` adds temporal evidence to the existing Core. Identity and
the eight intelligence dimensions remain unchanged. `trend_history` on each Core
card is the temporal read model, not a replacement for the conservative Trend
Readiness dimension. A calculable delta is different from reliable trend coverage.

## Collection contract

Future enrichment code calls only:

```python
record_trend_snapshot(
    con, target_type='VIDEO', target_id=str(video_id), video_id=video_id,
    observed_at=actual_capture_time, source='video_detail_observations',
    source_key=f'video_detail_observations:{observation_id}',
    metrics={'views': views, 'likes': likes, 'comments': comments},
    coverage={'basis': 'platform_counter_snapshot', 'original_observation': observation_id},
)
```

The caller owns the transaction and the authoritative observation ID. Backend
startup migrates the two additive tables. The writer accepts timezone-aware actual
capture timestamps and finite nonnegative counters or null; it never fills missing
values. Product/candidate references are explicit types, not implicit identity joins.
No existing collection path was activated or changed in this sprint.

The unique key includes target, normalized UTC timestamp, source and metric payload
SHA-256. A separate stable source key retains every provenance link and makes retry
idempotent. Changes to an existing source's counters or coverage are rejected;
explicit versioned corrections are required. Original records remain immutable.

## Offline bootstrap

```
.\.venv\Scripts\python.exe scripts/trend_history.py
```

The script imports existing search/detail observations and comment samples only.
It verifies a second import adds nothing, then checks protected domain tables,
original events and security state against the sprint checkpoint.

Persisted numeric strings reuse the existing strict metric parser (e.g. `31.2K`);
labels such as `Curtida`, `Comentários`, `Favoritos` remain null. Original raw
fields remain in their original source tables. Rounded counters have limited
precision; a zero delta can mean no change at displayed precision.

`first_seen` and `last_seen` are not converted into metric observations. Comment
samples are accumulated from actual comment capture timestamps using consumer
signals v2. Repeated author/text captures do not become new demand. The resulting
rate measures growth in **observed local sample coverage**, not publication-time
activity, total demand, purchases or sales. It does not drive Product Momentum.

## Cohorts

- PRODUCT_ENTITY: only approved identity occurrences; membership starts no earlier
  than entity approval and occurrence evidence.
- CANDIDATE: membership starts at candidate evidence time; explicitly unconfirmed.
- CATEGORY/SUBCATEGORY/PRODUCT_FAMILY: retrospective cohorts under the current
  classification. They do not claim the category was known at historical capture
  time and do not backfill market/category discovery dates.

Known-video counts describe observed cohort membership. Known creators accumulate
from actual reported creators in persisted snapshots; unknown creators remain
unknown. Creator concentration uses known creators only and does not establish
creator independence. Intent-author counts deduplicate known authors across cohort
videos. Cohorts overlap; do not sum them as independent products or market size.

Aggregate platform counters are emitted only when every active member has the
metric at **exactly the same capture instant**. Otherwise they stay null. No
last-value carry-forward, interpolation or invented baseline is used.

## Math and safeguards

Policy is centralized in `config/trend_history.json`.

- Two distinct valid timestamps for the same metric permit `(to-from)/seconds`.
  Platform rates use hours; known-video/creator and sampled-intent rates use days.
- Duplicate same-time values collapse with all evidence IDs retained. Conflicting
  values at one timestamp are excluded and exposed in `conflicting_timestamps`.
- Three valid points permit comparing two adjacent interval velocities. Acceleration
  magnitude uses the distance between interval midpoints. Relative/absolute stable
  tolerances are explicit. Different interval lengths are respected.
- Counter decreases are retained as observed deltas and marked as possible
  correction/removal, not asserted loss of market demand.
- Reliability is separate from magnitude. HIGH requires sufficient observations,
  span, videos, creators, creator coverage, controlled duplication and no conflicting
  metric timestamps. LOW can accompany a large observed rate.
- Category momentum additionally requires five videos, three creators and seven
  days. Current local cohorts do not meet that bar.
- Lifecycle stays DISCOVERED/EARLY_SIGNAL with weak coverage. Advanced transitions
  require broader longitudinal coverage. BREAKOUT, MAINSTREAM and SATURATED are
  reserved states and are never inferred by this v1 foundation.

## Optional adapters

`change_points` lazily imports ruptures only after 30 valid metric points spanning
seven days, with a minimum segment of five. No sufficient series means
INSUFFICIENT_HISTORY; missing package means ADAPTER_UNAVAILABLE. Results are
possible structural-change evidence in observation order, not market truth.

`IncrementalAdapter` accepts a River-compatible model (`learn_one`). It consumes
only real, non-null snapshot features once per snapshot ID, with a JSON seen-ID
checkpoint. The caller must checkpoint its model and cursor together. Bootstrap
does not create/train a River model or fabricate training points.

## Read-only API and UI

`GET /api/trend-history` returns coverage by target. Optional `target_type` and
`target_id` select one series. `/api/intelligence-core` includes per-video history.
Neither GET endpoint imports data, records snapshots or queues collection.

The TREND panel exposes actual observations, period, delta, velocity, acceleration,
creator/sample-intent momentum, lifecycle, quality and evidence. Insufficient cases
show “Ainda precisamos de mais observações.” No synthetic graph is rendered.

Gold labels are not read by the engine. Identity decisions, existing dimension
snapshots, visual evidence, supplier foundation, queues and the security latch
are outside its write scope. TikTok remains stopped.
