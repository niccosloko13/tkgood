# Search Result Enrichment

## Current numeric detail revision

`tiktok-video-detail-v2` separates loading labels from numeric values and waits
for stable counts. Real validation on eight videos: likes 87.5%, comments_count
87.5%, shares 100%, favorites 87.5%, views 0% (no count found). Metrics carry
source=video_detail, raw_value, method, deterministic confidence and timestamp.
See [VIDEO_DETAIL_METRICS.md](VIDEO_DETAIL_METRICS.md) for DOM evidence, exact
validation commands, coverage denominator, tests and remaining limitations.
The v1 validation below is historical, not the current numeric result.

## Authorized detail validation (2026-10-21)

After local DEV CONTROL loaded the pending author fix, READ_VIDEO_DETAIL commands
#13–#20 succeeded in sequence for all eight videos from search capture command:9.
Their separate detail observations contain creator and caption in 8/8 cases.
Dedicated count nodes returned only localized UI labels; no numeric metric was
invented (numeric detail coverage is 0% for views/likes/comments/shares/favorites).
This confirms metadata reading, not complete numeric detail extraction. Detail
source evidence retains confidence, raw values and server receipt timestamps.
The original search capture remains URL/ID 100%, creator/caption/views 50%,
thumbnail 0%. Its gate remains false. Library 12 / capture 8 / new 1 / updated 7
are unchanged by detail reads. The original enrichment sprint remains open.

CAPTURE RESULTS reads currently visible TikTok search cards. The user subsequently
authorized sequential READ_VIDEO_DETAIL navigation for already-collected videos,
reading visible metadata and counts only. No scrolling, comment bodies, TikTok
API requests, engagement, AI or product scoring are involved.

## Data model and migration

- `videos`: identity, `source=tiktok`, strong text `video_id`, canonical URL,
  best-known creator/display name/caption/thumbnail, UTC first/last seen times,
  and a JSON evidence dictionary. Strong `(source, video_id)` uniqueness takes
  priority over canonical URL fallback. A renamed creator handle does not create
  a new video when the numeric video ID matches.
- `search_captures`: capture ID (`command:<id>`), query, observed_at and version.
  Empty successful captures are recorded and report zero coverage.
- `search_observations`: internal video FK, capture ID, query, visual position,
  observed_at, raw_visible_text, sanitized card_snapshot, extractor_version,
  completeness, JSON structured fields and per-field evidence. Unique
  `(capture_id, video_id)` prevents identical retries within a capture; another
  command always preserves a new historical observation, including changed query
  or position. Retried command results remain idempotent through the result hash.
- `video_observations`: retained untouched as a legacy archive. A transactional,
  one-time `schema_migrations` marker imports its rows. No reset or deletion is
  required. Old first_seen_at and last_seen_at are preserved. Unknown historical
  positions remain null; history already overwritten by the old model is not
  reconstructed. Old fields without method evidence are explicitly unverified
  (`heuristic_text`, confidence 0), while URL-derived identity is verifiable.

Validate on a temporary SQLite backup without touching the source:
`.\.venv\Scripts\python.exe scripts/check_enrichment_migration.py`.
The existing 8 rows were preserved by this check before deployment.

## Extraction and field evidence

The current explicit extractor version is `tiktok-search-card-v2`. Live capture
`command:6` exposed a v1 boundary error: TikTok's `search_top-item` with
`role=button` was only the media tile. Its stored snapshots contained the video
overlay and no creator/description nodes. v2 climbs to a bounded logical parent
containing the same single video identity, including local sibling metadata.
The walk stops before another video, a list/grid/feed or page/account navigation;
an explicit article remains a boundary. No minified class name is required.
`extractSearchResultCard(card, position)` reads within that card only.
`extractSearchResults()` filters hidden/offscreen nodes, sorts visible anchors by
top then left (DOM order breaks ties), deduplicates by video ID and caps at 100.
Positions are 1-based within this visible capture, not an inferred global search
rank across unseen or previously scrolled results.

Each present structured field carries `value`, `confidence`, `source`, and UTC
`observed_at`; views also carries `raw_value`. The backend stamps observed_at at
receipt, independently of client clocks. Missing fields are null and do not
receive fabricated evidence. This is deterministic method quality, not an AI
probability or an estimate of content truth.

| Method | Confidence | Source |
|---|---:|---|
| Numeric video ID and canonical URL from valid video href | 1.00 | search_card |
| Creator from visible, card-local TikTok profile href | 0.98 | search_card |
| Creator/display name from a dedicated semantic label | 0.95 | search_card |
| Exact local @handle text outside caption/audio | 0.70 | heuristic_text |
| Caption from dedicated data-e2e description | 0.95 | search_card |
| Caption from a dedicated video-title link/heading | 0.75 | heuristic_text |
| Recognized count from a semantic views element | 0.98 | search_card |
| Visible image URL, video poster or semantic cover background | 0.95 | search_card |

Creator is never inferred from the video URL. A visible profile link is an
explicit creator signal; caption mentions and audio links are excluded. Generic
card text is never used as caption. Weak or ambiguous evidence stays null.

Views keeps exact visible `views_raw` and normalized integer `views`. K/M/B,
decimal dot/comma, grouped integers and explicit views labels are recognized.
Unknown/ambiguous formats preserve raw text and keep numeric views null. Shared
fixtures check the Python and JavaScript parsers against identical cases, including
zero and safe-integer limits. No missing metric is filled with zero.

The model also supports likes/comments_count/shares/favorites evidence when a
dedicated metric label really is visible in that search card. The authoritative
evidence shape is {value,raw_value,source,confidence,observed_at}; scalar legacy
count fields retain their raw strings for compatibility. Absent labels stay null
and have no fabricated evidence. A "Mais curtidos" badge is not a numeric metric.

`card_diagnostics` records viewport and card geometry, plus candidate counts,
visible counts and at most three bounding boxes for creator/description/views
nodes. It records no offscreen text. It distinguishes absent semantic nodes from
present nodes outside the viewport; it does not bypass lazy rendering, scroll or
open a video. A count found below the viewport still remains null in the capture.

Only thumbnail URLs are stored; no image files are fetched or cached by the
backend/extractor. The dashboard can render the remote URL as a lazy image with
no referrer. Snapshots contain only a bounded card fragment (12,000 characters),
visible text, safe tags and data-e2e/role attributes. They exclude scripts, inputs,
forms, hidden content, event handlers, URL attributes and account credentials.
The backend sanitizes again. Snapshots are not inserted as HTML into the dashboard.

## Precedence and history

`app/extraction.py::FIELD_PRECEDENCE` defines:
`video_detail > search_card > heuristic_text`.
Only search_card and heuristic_text are accepted from the search extractor.
The separate `tiktok-video-detail-v2` extractor accepts video_detail provenance;
legacy v1 remains accepted for compatibility and historical evidence.
Its evidence is kept in `video_detail_observations`, unique by command ID, and
merged into best-known library fields without changing search observations,
capture counters or search coverage. Missing views are never replaced with likes.
comments/external_source are reserved schema source names;
comments/external_source have no assigned precedence and cannot override fields.
Legacy payloads cannot assert new provenance.

For a known field, stronger source wins even if older; same source can update
when observed_at is equal/newer; weaker or null evidence never erases stronger
known data. Each observation still stores its own independent visible snapshot,
including nulls. Recent videos show best-known identity fields and the latest
observation's position/query/completeness. Coverage always uses that capture's
own observed fields, never merged fields borrowed from previous captures.

## Completeness, coverage and acceptance

`extraction_completeness` is a fraction in [0,1]: present video_url, video_id,
creator_username, caption, normalized views and thumbnail_url divided by six.
Zero views is present. Complete >=80%; Partial >=40% and <80%; Minimal <40%.

`GET /api/extraction/quality` returns latest capture metadata, sample size,
coverage percentages for those six fields, bucket counts and thresholds_met.
Legacy extractor captures cannot pass this sprint's gate. A successful empty
capture replaces the prior coverage with zeros. Coverage is not the accumulated
database's coverage. RECENT VIDEOS uses `—` for missing fields.

The dashboard distinguishes four persisted metrics:

- Library videos (`library_total`): every unique identity retained in SQLite.
- Current capture (`current_capture`): observations in the last successful capture.
- New this capture (`new_this_capture`): identities first inserted by that capture.
- Updated / duplicates (`updated_duplicates`): already-known identities observed again.

Capture counters are saved atomically with observations. For existing command
captures, migration derives counts from each observation timestamp versus the
video's persisted first_seen_at. Imported legacy snapshots with unavailable
history keep null counters, displayed as `—`. Retries cannot change saved counts.
No historical video or observation is deleted to make a display counter smaller.
Inspection of the actual pre-v2 database confirmed Library 11, Current 8, New 3,
Updated 5, while preserving all 11 videos, 16 observations and 8 legacy rows.

Live acceptance needs at least eight current cards, URLs/IDs 100%, creator >=75%,
caption >=70%, views >=75%, plus SEARCH/CAPTURE/OPEN working in normal Chrome.
Thumbnail coverage has no failure threshold. Automated fixtures are not real
coverage measurements. If a live metric fails, inspect the bounded card snapshots
from `/api/videos/recent`, fix the local DOM method and repeat manual capture.

## Validation status

The real v1 capture command:6 failed acceptance: 8 results; URL/ID/thumbnail 100%,
creator/caption 0%, views 50%. Raw snapshots proved the chosen media subtree had
no creator/description, and only the first four snapshots included visible views.
This is not sufficient evidence that VIDEO DETAIL is required. v2 live capture
and visibility diagnostics must be examined before concluding a field is absent
from the search card. Coverage targets are unchanged; the sprint remains open.

### Real v2 investigation — command:9 (2026-10-21)

SEARCH navigated the normal Chrome tab to `search?q=home+gadgets`; the bridge
reported readyState complete. The read returned 8 current results, Library 12,
New 1, Updated 7. URL/ID coverage stayed 100%; creator/caption became 50%, views
remained 50%, and current thumbnail coverage was 0%. These are real measurements,
not fixture results or accepted targets.

The actual sanitized snapshot shows this card-local relationship:

```html
<div>
  <div data-e2e="search_top-item" role="button">
    <a><strong data-e2e="video-views">31.2K</strong></a>
  </div>
  <div data-e2e="search-card-desc">
    <div data-e2e="search-card-video-caption">
      <span data-e2e="new-desc-span">...</span>
    </div>
    <a data-e2e="search-card-user-link">
      <p data-e2e="search-card-user-unique-id">...</p>
    </a>
  </div>
</div>
```

`search-card-desc` is a metadata wrapper, not exclusively caption text. Its
author must not be rejected as a caption mention, and the whole wrapper must not
be used as caption (it includes author/date). A regression fixture now reproduces
this structure and gives profile href priority over a potentially ambiguous
display alias. No CSS class or global page text is involved.

The viewport was 1536 x 730 CSS pixels. Measured geometry explains the remaining
four missing rows without guessing at their values:

| Search positions | Views top–bottom | Caption top–bottom | Visibility |
|---|---|---|---|
| 1–4 | 377.9–393.9 | 412.5–430.5 | inside viewport |
| 5–8 | 780.3–796.4 | 814.9–833.0 | below viewport bottom 730 |

All eight cards contained a semantic views node; only four were in the viewport.
This was not a K/M/B parser failure. Offscreen values were left null. The next
read needs at least eight complete cards visible (manual window/zoom adjustment)
to test all fields under the existing visible-only policy. These fields are
present in search-card DOM; this evidence does not justify claiming they require
VIDEO DETAIL. The sprint remains open and thresholds have not been reduced.
