# BABI V1 — Phase 3 validation run

Run completed on 2026-10-26 using the existing `DiscoveryRunner` in strict
search-only mode. No video card, detail page, comments, or creator profile was
opened.

## Safety and scope

- Initial passive validation: `tiktok_tab=true`, page `HEALTHY`, session
  `CONFIRMED`; Companion build `525328dc01f89eca`.
- The existing explicit manual-CAPTCHA release was used only after that healthy
  passive validation. The historical CAPTCHA event and its associated temporary
  quarantine were retained.
- Global security ended `OK` (no browser-security latch).
- Direct Video Enrichment remains `PAUSED` with reason
  `REPEATED_CHALLENGE_AFTER_VIDEO_NAVIGATION`.
- No 403, CAPTCHA, challenge, verification, or confirmed logout appeared in
  this run.

## DiscoveryRunner results

Stage 1 (`home gadgets`) completed first as the required validation gate:

| scope | results | new videos | duplicates | observations | snapshots |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage 1 | 8 | 0 | 8 | 8 | 8 |
| Stage 2, five-query pack | 24 | 2 | 22 | 24 | 24 |
| Validation-cycle total | 32 | 2 | 30 | 32 | 32 |

Stage 2 query metrics:

| query | results | new | duplicates | blocked references | snapshots |
| --- | ---: | ---: | ---: | ---: | ---: |
| home gadgets | 8 | 0 | 8 | 2 | 8 |
| home finds | 4 | 2 | 2 | 1 | 4 |
| useful home products | 4 | 0 | 4 | 2 | 4 |
| kitchen gadgets | 4 | 0 | 4 | 1 | 4 |
| cleaning gadgets | 4 | 0 | 4 | 2 | 4 |

Stage 2 stopped normally at `MAX_QUERIES`. Individual target URLs were never
opened; blocked-target figures are visible-result references only.

## Intelligence recomputation

The deterministic offline engine recomputed from persisted evidence at
`2026-10-26T04:15:57Z`. It found no lifecycle, momentum, acceleration, or
saturation changes relative to the existing read model. The new observations
increased freshness only; they did not produce unsupported claims.

Top Opportunities before and after were materially unchanged:

| candidate | lifecycle | momentum | query spread | creator spread | velocity | acceleration | saturation |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| Soap dispenser | EMERGING | HIGH | 5 | 2 | RISING | STABLE | LOW |
| dish brush | EMERGING | HIGH | 5 | 2 | RISING | STABLE | LOW |
| Burger Patty Maker | EMERGING | MEDIUM | 2 | 1 | STABLE | STABLE | MEDIUM |
| fruit spinner | EMERGING | MEDIUM | 2 | 1 | INSUFFICIENT | INSUFFICIENT | INSUFFICIENT |
| long-handled floor brush | EMERGING | MEDIUM | 3 | 1 | STABLE | STABLE | MEDIUM |

Watchlist remains deterministic and separate from the ranked opportunities:
`escova` (EARLY_SIGNAL), `3 in 1 Window Cleaner` (EARLY_SIGNAL), and
`Portable Dryer` (SATURATED).

## Prediction checkpoints / backtest

All 14 current checkpoint evaluations remain `UNKNOWN` at each 6h, 24h, and
72h horizon: no persisted future candidate observation is available for the
required window. This is the intended no-future-leakage outcome; no score or
backtest conclusion was invented.

## Verification

- Targeted recovery/quarantine regression suite: `36 passed`.
- Four third-party framework deprecation warnings were reported (FastAPI event
  hooks and legacy `websockets` APIs); none is a Phase 3 functional regression.

## Final state / recommendation

- Final page: `HEALTHY` search page (`cleaning gadgets`)
- Final session: `CONFIRMED`
- Global security: `OK`
- Search-only collection: available through the existing safety gate
- Direct Video Enrichment: `PAUSED`

Recommended next step: wait for the existing prediction horizons to acquire
enough persisted future observations, then run the existing offline evaluation.
Do not resume direct-video enrichment without explicit human authorization and
a separately healthy safety check.
