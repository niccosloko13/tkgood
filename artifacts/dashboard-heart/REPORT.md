# Dashboard Heart Refresh

## Scope

The overview is now a decision cockpit: it leads with the current operating
mode, makes persisted signals easier to scan, and keeps collection controls
and technical detail secondary. This is a presentation-only change.

## Changes

- Added an executive overview header with the current safe operating mode.
- Reworked hierarchy, spacing, KPI cards, status chips, search controls,
  opportunity cards, recent-video cards, candidate cards, and responsive rules.
- Rebuilt the read-only opportunity view around understandable evidence:
  observations, search spread, creator spread, motion, explanation and limits.
- Preserved pt-BR number formatting and updated the opportunity UI test to
  assert the current Portuguese watchlist label.

## Compatibility and safety

- No backend route, collector command, browser command, or data schema changed.
- The opportunity view still performs only `GET /api/opportunities` and emits
  no content or collection command.
- Safety Contract, security latch, quarantine, search-only behavior and the
  paused direct-video enrichment mode were not changed.
- Existing IDs and action controls remain in the static dashboard markup.

## Validation

- JavaScript focused dashboard suite: 24 passed, 0 failed.
- Python session/safe-collection suite: 23 passed, 0 failed.
- The static page was validated through DOM tests. Manual external-browser
  inspection was intentionally not used because the requested connection model
  forbids Computer Use/external Chrome validation.

## Remaining limitation

This refresh does not fabricate intelligence. Fields that have no persisted
evidence remain visibly unavailable rather than being converted into a score.
