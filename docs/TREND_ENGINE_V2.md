# Trend Engine v2

`app.trend_engine_v2` is an offline deterministic read model. It reads persisted
candidate evidence, search observations and candidate trend snapshots. It does
not navigate the browser, import visual dependencies, consult Gold Set labels,
write raw observations or change Safety state.

## Inputs and time boundary

Candidate membership is only active after its `product_candidate_evidence.observed_at`.
Every historical calculation accepts `as_of` and uses observations, memberships
and snapshots at or before that time. This makes prediction checkpoints and their
evaluations resistant to future leakage.

## Metrics

- Recurrence is the count of distinct `capture_id` values. Duplicate cards in
  one capture cannot increase it.
- Query and creator spread count normalized, observed values only.
- Duplicate density is `1 - unique_video_count / observation_count`.
- Velocity for each counter uses `(counter_t2 - counter_t1) / elapsed_hours`,
  only with two valid numeric candidate snapshots.
- Acceleration is the difference between the final two velocities, only with
  three points. Negative counter deltas are kept and exposed as a quality risk.
- Content age is never inferred. `babi_detection_age_hours` is explicitly
  separate from unavailable original content age.

Thresholds live in `config/trend_engine_v2.json`. They are conservative rules,
not an opaque weighted score. Momentum, evidence quality, saturation and
lifecycle remain separate dimensions.

## Lifecycle and ranking

`DISCOVERED` requires no proof beyond a local observation. `EARLY_SIGNAL` is
recurrence without enough evidence. `EMERGING`, `ACCELERATING` and `BREAKOUT`
require increasingly stronger recurrence, spread, observed velocity and evidence.
`SATURATED` requires multiple repetition signals; `DECLINING` requires observed
falling velocity and acceleration. Ranking sorts those explicit dimensions and
penalizes high saturation; it has no single Babi score.

## Durable outputs

- `top_opportunities`: idempotent candidate read model.
- `trend_change_events`: only state transitions or spread increases, keyed to
  the source hash to avoid repeat events.
- `prediction_checkpoints`: immutable evidence/metric/WHY snapshots for high
  momentum emerging-or-later candidates.
- `prediction_evaluations`: 6h, 24h and 72h outcomes when the future window is
  actually available. Missing future coverage is `UNKNOWN`, never a failure.

DiscoveryRunner calls `recompute` after a persisted search capture. That call is
offline database work and does not relax the Safety contract.
