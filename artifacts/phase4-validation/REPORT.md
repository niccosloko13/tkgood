# BABI V1 — Phase 4 validation window (interim)

## Scope

This records the first real validation cycle, at 2026-10-26T04:23Z–04:25Z. It
used only the canonical `DiscoveryRunner` in search-only mode and the existing
Casa query pack. No direct video, comments, creator profile, visual, supplier,
ML, recovery, scoring, query, or threshold feature was added.

Direct Video Enrichment remains `PAUSED`.

## Safety

- Pre-cycle passive check: `tiktok_tab=true`, `PAGE=HEALTHY`, `SESSION=CONFIRMED`.
- Global security: `OK`; no active latch before or after collection.
- Final URL: `https://www.tiktok.com/search?q=cleaning+gadgets`.
- No 403, CAPTCHA, challenge, verification prompt, or confirmed logout occurred.
- No content action was retried.

## Cycles and persisted evidence

| measure | value |
| --- | ---: |
| Completed Stage 2 cycles in this window | 1 |
| Stage 2 queries | 5 |
| Stage 2 results | 24 |
| New videos | 1 |
| Duplicates | 23 |
| Search observations added | 24 |
| Trend snapshots added | 24 |
| Required Stage 1 gate observations/snapshots | 8 / 8 |

The cycle total, including its Stage 1 gate, is 32 observations and 32 snapshots.
Stage 2 ended normally at `MAX_QUERIES`.

## Per-query duplication

| query | results | new | duplicates | duplicate rate |
| --- | ---: | ---: | ---: | ---: |
| home gadgets | 8 | 0 | 8 | 100% |
| home finds | 4 | 0 | 4 | 100% |
| useful home products | 4 | 1 | 3 | 75% |
| kitchen gadgets | 4 | 0 | 4 | 100% |
| cleaning gadgets | 4 | 0 | 4 | 100% |
| total | 24 | 1 | 23 | 95.8% |

This is another high-duplication cycle. It is evidence of possible query-pack
saturation, not a reason to change the validated queries during Phase 4.

## Candidate evolution since the Phase 3 endpoint

No candidate changed lifecycle, momentum, recurrence bucket, query spread,
creator spread, velocity, or acceleration. No `EARLY_SIGNAL` moved to
`EMERGING`, no candidate moved to `ACCELERATING`, and no candidate lost momentum.
`fruit spinner` changed only from `INSUFFICIENT` to `MEDIUM` saturation evidence;
its lifecycle and momentum did not change.

## Final Top Opportunities

| candidate | lifecycle | momentum | query / creator spread | velocity | acceleration | saturation |
| --- | --- | --- | --- | --- | --- | --- |
| Soap dispenser | EMERGING | HIGH | 5 / 2 | RISING | STABLE | LOW |
| dish brush | EMERGING | HIGH | 5 / 2 | RISING | STABLE | LOW |
| Burger Patty Maker | EMERGING | MEDIUM | 2 / 1 | STABLE | STABLE | MEDIUM |
| fruit spinner | EMERGING | MEDIUM | 2 / 1 | INSUFFICIENT | INSUFFICIENT | MEDIUM |
| long-handled floor brush | EMERGING | MEDIUM | 3 / 1 | STABLE | STABLE | MEDIUM |

Watchlist: `escova` remains `EARLY_SIGNAL`; `3 in 1 Window Cleaner` remains
`EARLY_SIGNAL`; `Portable Dryer` remains `SATURATED`.

## Backtest status

| horizon | GREW | STABLE | DECLINED | UNKNOWN |
| --- | ---: | ---: | ---: | ---: |
| 6h | 0 | 0 | 0 | 26 |
| 24h | 0 | 0 | 0 | 26 |
| 72h | 0 | 0 | 0 | 26 |

No checkpoint has sufficient persisted future candidate evidence yet. `UNKNOWN`
is the correct anti-leakage result, not a failed prediction.

## Conclusion

There is not yet enough elapsed-time data to claim predictive value. This first
cycle confirms that safe search-only collection and deterministic recomputation
work without regression, but a validation window requires future cycles separated
in real time and subsequent 6h/24h/72h maturity. The next safe action is to
wait for a later operator-authorized cycle; do not run back-to-back collection
merely to inflate sample size.
