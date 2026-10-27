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
- [x] User confirmed RECENT VIDEOS with 8 videos, stable count on recapture and duplicate-update logs (2026-10-21)
- [ ] Evidence snapshots/structured records
- [x] No social interaction

## v0.3 — Guided Discovery
- [ ] Mission query plan
- [ ] Search route scoring
- [ ] Signal Yield
- [ ] Diversity guard
- [ ] Information gain

## Search Result Enrichment — current sprint
- [x] Strong video identity and canonical URL fallback
- [x] Separate videos, capture history and search observations; preserve legacy archive
- [x] Isolated card detection and structured extraction without cross-card text
- [x] Creator/caption/normalized views/thumbnail/visual position
- [x] Per-field method confidence, source and timestamp; explicit source precedence
- [x] Versioned extractor, sanitized card snapshots and raw visible evidence
- [x] Completeness and latest-capture coverage in dashboard
- [x] Automated migration check preserves the existing 8 videos on a temporary backup
- [ ] Real capture >=8 cards with URL/ID 100%, creator >=75%, caption >=70%, views >=75%
- [ ] User visual acceptance and approval to close this sprint

Real v1 validation failed (8 results; creator/caption 0%, views 50%). v2 corrects
the media-only boundary and adds visibility diagnostics. Acceptance targets have
not changed. Dashboard now separates Library / Current capture / New / Updated
using persisted counts; historical videos and observations are retained.

The user subsequently authorized bounded READ_VIDEO_DETAIL for existing library
videos. Implementation and automated tests exist; real validation remains open.
Detail evidence does not count toward search-card coverage. The subsequent comments
authorization is recorded below. Engagement, AI, resolver, scoring and trend engine
remain excluded.

## Local DEV CONTROL
- [x] Owned backend supervisor, logs, process identity and graceful restart
- [x] Local-only authenticated development queue, drain and timeouts
- [x] Companion self-reload with durable storage flag and TikTok-only refresh
- [x] Build identity in worker/content heartbeats, panel and devctl status
- [x] Real reload-all returned READY; detail commands #13–#20 succeeded (8/8)
- [x] Numeric detail metrics v2: real 8-video sample, likes/comments 87.5%, shares 100%, favorites 87.5%
- [ ] Views in detail: no visible count found in the current eight-video sample; remains null

## Comments sampling read-only
- [x] Explicit semantic command for an existing enriched video; default 30/max 100
- [x] Visible row evidence, nullable fields, raw likes/timestamp, method/version/confidence
- [x] Comments-container-only bounded scrolling; no reply expansion or engagement
- [x] Historical SQLite samples and deterministic configurable en/pt/es lexical signals
- [x] Dashboard sample/unique/questions/price/link/buy/problem counters
- [x] Real v2 validation: many 30, intermediate 15, few 10 comments; total 55
- [x] Text/likes coverage 100%; author/timestamp 54/55 (98.18%); IDs unavailable
- [x] Full regression suite: 94 Python tests and 51 Node tests passed
- [ ] User review of the delivered comments sampling sprint

No AI, sentiment, buyer-intent model, product detection, profiles or clustering.

## Creator / profile enrichment and independence
- [x] Public semantic READ_CREATOR_PROFILE for existing observed library creators
- [x] Separate creators, video_creators and append-only creator_profile_observations
- [x] Canonical identity, raw/normalized counts, deterministic confidence/provenance
- [x] Public link evidence without following external links
- [x] Configurable size buckets and profile/per-video ratios
- [x] Transparent creator-only heuristic indicator, components and version
- [x] Creator drawer and collapsed video-detail section; same six main areas
- [x] One-creator validation followed by five real creators (commands 66–70)
- [x] Username/URL, followers, display name, total likes coverage: 5/5 (100%); bio: 4/5 (80%)
- [x] Full regression: 100 Python and 65 Node tests passed; PT-BR/ar-EG drawer checks passed
- [x] Existing database/history/approved detail and comments preserved
- [ ] User review of this delivered sprint

Sources, formula, null policy and real examples: CREATORS.md. Avatar/video_count
were not captured in the five current layouts and remain null. External links
were observed for 4/5 creators. Optional profile recent-content sampling is omitted.
No AI, product detection/clustering, Gold Score, trend engine, profile scrolling
or engagement was added. This authorization supersedes the earlier exclusion of
profile reads only for this bounded, explicit enrichment flow.
