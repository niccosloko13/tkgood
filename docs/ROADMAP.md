# Product Hunter — TikTok Roadmap

## v0.1.4 — Normal Chrome Foundation
- [x] Local dashboard
- [x] Normal Google Chrome profile
- [x] Manual TikTok login
- [x] Read-only Chrome Companion extension
- [x] Extension heartbeat
- [x] Visible page health signals
- [x] SQLite events/missions
- [x] No Playwright on TikTok
- [x] No engagement actions

## v0.2 — Read-only TikTok Capture
- [x] Capture search result cards currently visible (manual READ_SEARCH_RESULTS, max 100)
- [x] Capture video URL/caption/creator/visible metrics; missing values remain null
- [x] Capture current search query
- [x] Deduplicate observations by canonical video URL; preserve first_seen_at
- [x] VIDEOS unique count and RECENT VIDEOS with OPEN links
- [x] Atomic command acknowledgement, observation storage and capture logs
- [x] Live Chrome capture on current TikTok DOM: 8 inserted, then 8 duplicates updated (API/log verified)
- [ ] User confirmation of RECENT VIDEOS rendering in the live dashboard
- [ ] Evidence snapshots/structured records
- [x] No social interaction

## v0.3 — Guided Discovery
- [ ] Mission query plan
- [ ] Search route scoring
- [ ] Signal Yield
- [ ] Diversity guard
- [ ] Information gain
