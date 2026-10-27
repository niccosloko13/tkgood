# VIDEO_ID RECENCY VALIDATION

## Decision

**REJECTED**

## Method considered

`int(video_id) >> 32` interpreted as a Unix UTC timestamp was evaluated only
as an untrusted hypothesis. No production recency field was written from it.

## Validation set

- Samples with a locally persisted, independently trustworthy `create_time` or
  publication timestamp: **0**.
- Therefore mean, median, maximum error and threshold percentages are **N/A**.
- Gold Set, fixtures and historical artifacts were searched only as validation
  sources; none supplied the required paired publication timestamp.

## Why rejected

Without paired ground truth, deriving a timestamp from a platform identifier
would be an unverified inference. Observation/capture timestamps are not video
publication timestamps and were not used as substitutes.

## Impact on Viral Products 72h

- Reprocessed by this experiment: **0** (method not approved).
- Existing 59 search-only results remain `RECENCY_UNKNOWN`.
- `<24h`, `24-48h`, `48-72h`, `>72h`, and `BORDERLINE`: **0** by this source.
- No Top Picks were promoted.

## Guardrails retained

- No video was opened.
- No new TikTok collection was performed.
- Direct Video Enrichment remains paused.
- Ranking, lifecycle, Trend Engine and Safety Contract were not changed.
