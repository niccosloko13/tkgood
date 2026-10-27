# Recovery + Search-only validation

## Recovery

- A passive recovery check collected two fresh, matching heartbeats from the
  existing TikTok tab (`618200753`).
- Both samples reported a complete, healthy TikTok home, confirmed session,
  no active challenge and no HTTP 403 indicator.
- The historical `HTTP 403: https://www.tiktok.com/` latch was released as an
  explicit operator action. The previous incident and its validation evidence
  were retained in security history.

## Search-only execution

- Query: `produtos virais hoje`
- Command: `READ_SEARCH_RESULTS #122`
- Real existing TikTok tab: `618200753`
- Final search URL: `https://www.tiktok.com/search?q=produtos+virais+hoje`
- Results observed: 4
- New videos: 4
- Duplicates: 0
- Trend snapshots: 4
- Navigation stopped after one bounded visible viewport (maximum 10 results,
  zero scroll, zero individual video navigation, zero engagement).

## Safety

- Final page: healthy
- Final session: confirmed
- Global security: OK
- Direct Video Enrichment: PAUSED
- No CAPTCHA, challenge, logout or 403 occurred during this run.

## Flow change

- `Reverificar` now starts the passive two-heartbeat recovery check and, only
  after it succeeds, issues the matching explicit release request. A heartbeat
  still cannot release a latch by itself.
- A user-triggered search under the recovery guard is routed through
  `DiscoveryRunner`, preserving one query, a maximum of ten visible results,
  zero scroll and the existing hard-stop behavior.
- The extension now requests focus for the existing TikTok tab during bounded
  search navigation. No browser, profile or tab is created. The completed run
  was not repeated after this focus-only adjustment because the bounded runner
  deliberately disallows retrying a completed Stage 1.

## Validation

- JavaScript safety/connection suite: 25 passed, 0 failed.
- Python recovery/discovery/session suite: 26 passed, 0 failed.
