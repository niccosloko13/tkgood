# Creator / profile enrichment

`READ_CREATOR_PROFILE` reads only public header metadata of a creator already
associated with a captured library video. It accepts `video_url`, not an arbitrary
profile URL or selector. The server resolves the observed username, queues its
canonical public profile and pins the originating video. The Companion opens the
profile, waits for visible metadata, reads it and returns to that library video.
No profile/video grid scroll, external-link navigation, button click, follow,
message, comment, reply, like or other engagement is performed. A visible login or
security challenge stops the read and leaves it for human intervention.

## Identity, history and URLs

`creators` stores platform=tiktok, normalized username, canonical profile URL,
display name, bio, avatar URL, followers/following/total likes/video count, public
external link, explicit category/type, first/last seen and extractor version.
Username is case-folded; query strings/fragments and trailing slash are removed
from TikTok profile identities. Username is the primary dedup key, canonical URL
the fallback. There is no stable TikTok account-ID discovery or username-change
resolution. Only previously observed creator usernames with method confidence >0
are linked; an author is never inferred from the video URL alone.

`video_creators` relates existing videos to creators without changing video rows.
`creator_profile_observations` appends each successful command's complete snapshot:
counts, bio/link, raw visible evidence, structured fields, links, provenance,
deterministic signals and the exact configuration used. Command IDs are unique;
acknowledgement retries are idempotent. Old observations are never overwritten.
Creator metadata columns project the latest snapshot, including nulls; older
nonnull values remain in history. API/UI performance uses the **latest observation**,
so an unavailable new follower count cannot silently reuse an old denominator.
UI likewise displays latest values. Explicit empty-bio placeholders are retained
in raw evidence, but do not count as a biography.

Existing video/search/detail/comment tables remain untouched. Migration widens
only the command CHECK while preserving IDs, options, hashes and states, then
creates the three new tables. No database reset is required.

## Visible extraction and provenance

Version: `tiktok-creator-profile-v1`. Stable user-title/user-subtitle headings
can swap roles in the current TikTok DOM. A visible heading must match the requested
profile username; the other identifies display name. The logical header includes
local bio/avatar/count/link siblings, stopping before navigation or the video grid.
No global page text fills a profile field. Only explicit semantic count nodes
provide followers/following/total_likes/video_count; counting visible grid cards
is not a substitute for total video_count.

Every important observed field carries value, raw_value, normalized_value for
counts, source=creator_profile, confidence, method, observed_at and extractor_version.
The backend stamps receipt time. Fixed method confidence: username and verified
route .99; semantic counts .98; text/bio/display/category .95; visible href and
semantic avatar .98. A unique, visible square header image uses the explicitly
weaker visible_header_image method (.90). Confidence describes extraction method,
not the account's authenticity or the truth of its bio.

K/M/B arithmetic is exact, including decimal point/comma with a suffix. Examples:
31.2K=31200, 31,2K=31200, 1.4M=1400000, 2B=2000000000. Bare 1,234 or 1.234 is
ambiguous and remains null, with raw text preserved. Missing fields stay null.

Visible header links preserve their original public HTTP(S) href, label, source,
confidence, observation time and version. Public TikTok bio redirects are recorded
as redirects, without resolving/following them. Credentials and sensitive URL
parameters are rejected. External/shop/commercial signals are literal matches
against centralized configuration, not claims that an account is an affiliate.
Bio text alone does not prove an external link exists. No external page is opened.

## Deterministic indicators

All thresholds and weights live in `config/creator_signals.json`.

| Bucket | Followers |
|---|---|
| micro | 0–9999 |
| small | 10000–49999 |
| medium | 50000–249999 |
| large | 250000–999999 |
| mega | >=1000000 |

Profile signals: has_external_link, has_commercial_link, has_shop_signal,
follower_count, total_likes, video_count, followers_to_video_ratio and
likes_per_follower_ratio. Division requires denominator >0. No missing count is zero.

Video ratios divide existing views/likes/comments_count/shares evidence by the
latest observed followers. Numerator method confidence must be >=0.6 (configured).
Legacy evidence with zero confidence is retained but cannot produce a derived
ratio/score. Numerator and denominator observation times are exposed separately;
these are ratios between snapshots, not contemporaneous growth measurements.

Creator Independence v1, when both views and likes ratios exist:

```
70 × min((views/followers)/10, 1)
+ 20 × min((likes/followers)/0.5, 1)
+ size bonus (micro 10, small 8, medium 5, large 2, mega 0)
```

Clamp to 0–100 and round to two decimals. Ratios use six decimals; the API returns
components, parameters and formula version. Missing/zero denominator or either
required reliable numerator yields null. A small account with zero views and
likes gets only its configured size bonus, not a claim of successful performance.
This is an explainable heuristic indicator, **not evidence of causal independence**,
product quality, buyer intent or a Gold Score. No AI or product entity exists.

## API and UI

- POST /api/commands: `{"type":"READ_CREATOR_PROFILE","video_url":"..."}`.
- Successful acknowledgement: creator_profile, mutually exclusive with existing
  capture/video_detail/comments_sample result bodies. Wrong type/owner/profile,
  unclaimed/expired state or modified retries cannot insert observations.
- GET /api/creators: linked identities, latest snapshot, signals and related videos.
- GET /api/creators/{creator_id}: the same strict response for one creator.

Click creator in VÍDEOS to open its drawer. The existing video drawer also has a
collapsed creator section. Both preserve profile/video URLs, show missing values
as — and offer the explicit profile-read command. No new main navigation area or
separate page is added. PT-BR and ar-EG/RTL remain supported.

CLI: `python scripts/read_creator_profiles.py --limit 1`, then `--limit 5`.
Optional `--video-url URL` selects a specific library video. The helper reads at
most five creators sequentially and stops on the first failure. DEV CONTROL loads
updates; no manual backend/extension restart is needed.

The optional 12-video profile-content sample is deliberately not implemented.
There is no grid traversal, profile scrolling, product clustering, AI or scoring
beyond the explicitly requested creator indicator. Real results are recorded in
`.runtime/creator-enrichment-validation.json`; see ROADMAP.md for acceptance.

## Real validation — 2026-10-21

The final build `812977fc8a8e3590` read five distinct creators through commands
66–70, after command65 passed the one-creator empty-bio check. All five completed and returned
to their originating library videos, without engagement. Earlier failed reads
are explicitly FAILED and inserted no profile observation; retries are separate
historical commands, not fabricated success.

| Creator | Followers (raw) | Total likes | Bucket | Views/followers* | Score* |
|---|---:|---:|---|---:|---:|
| @airlandolists | 2200000 (2.2M) | 21800000 | mega | 0.000295 | 0.01 |
| @anya.bumag | 893400 (893.4K) | 26300000 | large | 0.093127 | 6.37 |
| @goodfinds366 | 1187 (1187) | 5177 | micro | null | null |
| @megashopping39 | 13000 (13K) | 79500 | small | 0.126923 | 13.96 |
| @elnazhamai | 529500 (529.5K) | 14000000 | large | 0.521435 | null |

*These examples refer to each creator's first related library video in the saved
report, not an aggregate across their videos. Good Finds has a legacy views value
with confidence0, so no views ratio or score is claimed. Elnaz's selected video
has no reliable likes observation. Its views ratio exists but its score stays null.

Coverage over these five latest observations: username/profile_url, followers,
following, display_name and total_likes **100% (5/5)**; bio **80% (4/5)**;
external_link **80% (4/5)**. MEGA SHOPPING exposes TikTok's empty-bio placeholder:
it is retained in raw evidence and the structured bio is null. Earlier diagnostic
snapshots remain in history; coverage uses only the latest corrected observations.
No explicit total video counter was captured (0/5), and no avatar was captured in
these five live layouts (0/5). These remain null; fixture support is not evidence
of real avatar coverage. No recent-content profile sampling was added.

Preservation verification compared protected tables against a pre-sprint SQLite
backup: all 17 videos, 32 search observations, 18 detail observations, 9 comment
samples/149 comment observations, 11 captures, 8 legacy rows and 2 missions were
byte-for-byte equivalent when serialized. All 47 pre-existing commands retained
their IDs, states, options and result hashes. Approved detail/comment extractor
files and their repository modules retained their SHA-256 hashes. Integrity and
foreign-key checks passed.

Full regression suite: **100 Python tests and 65 Node tests passed**. Browser
checks on the local dashboard verified six-area navigation and no horizontal
overflow in 60 PT/Arabic viewport combinations, plus creator/video drawers,
related URLs, real follower counts and retained collapsible state in six additional
desktop/tablet/mobile PT-BR/ar-EG combinations. Browser testing is confined to
localhost; real TikTok reads run exclusively through the normal Companion.
