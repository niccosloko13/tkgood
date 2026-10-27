# Visible comments sampling

`READ_COMMENTS_SAMPLE` accepts a canonical URL of an existing enriched library
video and target_count (default 30, strict integer 1–100). Use the VIDEO DETAIL
SAMPLE COMMENTS (30) button or `python scripts/sample_comments.py VIDEO_URL --target 30`.
Development updates use `python scripts/devctl.py reload-all`, without manual reloads.

## Extraction and bounds

The extractor is `tiktok-comments-visible-v2`. Stable comment-level semantic seeds
identify each local row, including the current TikTok structure where the seed is
a text span and its parent contains author/footer. It reads only visible text,
the row's public profile href, semantic/local accessible likes and timestamp text.
It never fills fields from page-global text. Clipped rows cannot turn the nearby
Responder label into a comment. Numeric likes preserve likes_raw and normalize K/M/B.
Absent fields are null; timestamps remain unparsed public strings such as `1 d atrás`.
Confidence is deterministic 0.95 for this semantic-row method, not a prediction.

Only the fixed semantic comments opener may be activated. Scroll is restricted to
the bounded comments container, never the page/feed. Replies are recognized only
when already visible; reply expansion and the composer are never activated.
Sampling stops at the requested target, exhaustion/stagnation, no scroll region,
20 scroll steps, or a 45-second sampling deadline. Queue expiry is 90 seconds.
Navigation/readiness waits are bounded. Security challenges stop the read.

## Storage and evidence

`comment_samples` stores video/command identity, receipt time, target, stop reason,
scroll count, extractor version, signals, the exact terms configuration and bounded
diagnostics. `comment_observations` stores public comment ID when available, video,
author, text, likes/raw likes, timestamp, position, nullable is_reply/reply_count,
source `comments_visible`, observed_at, raw_visible_text, method, confidence and version.
Diagnostics include only bounded sanitized public-row fragments, never a whole page,
inputs, credentials or account state. Existing videos/detail metrics are untouched.

Within a sample, public comment ID is preferred; otherwise the visible tuple
(author, text, timestamp, reply status) is hashed. Repeated DOM nodes/React replacements
do not inflate counts. Without public IDs, genuinely identical anonymous comments
can merge; the fallback is not proof of global comment identity. New commands retain
separate historical samples. Retrying the same acknowledgement does not insert again.

## Objective signals

`config/comment_terms.json` separates en/pt/es price/link/buy/problem term lists.
Normalization uses NFKC, case folding and whitespace; escaped literal terms use
word boundaries. A comment matching several terms/languages counts once per total
category. Language buckets describe matching term lists, not inferred language.
Question count checks literal question marks. Unique commenters counts known
usernames only. Duplicate ratio = 1 − unique normalized texts / sampled comments.
These counts do not infer sentiment, intent, negation or product relevance.

## Real validation — 2026-10-21

| Video ID | Sampled | Known unique commenters | Questions | Price | Link | Buy | Problem |
|---|---:|---:|---:|---:|---:|---:|---:|
| 7462746836533677358 (many) | 30 | 30 | 10 | 1 | 11 | 3 | 0 |
| 7672558839388048661 (intermediate) | 15 | 12 | 1 | 0 | 0 | 2 | 0 |
| 7698002338652507405 (few) | 10 | 10 | 0 | 1 | 0 | 0 | 0 |

Latest v2 samples: commands 45, 44 and 42. Total 55 comments. Text, likes and reply
structure: 55/55 (100%). Author and timestamp: 54/55 (98.18%). Public comment IDs:
0/55, so null throughout. Duplicate-text ratios: 6.67%, 0%, 0% respectively.
The first reached target30; the other two stopped with no more loaded comments.
This does not claim all comments on those videos were read; collapsed replies
remain untouched. Earlier diagnostic samples are preserved and excluded from these
latest-v2 figures. Local report: `.runtime/comments-sampling-validation.json`.

Full tests: `.venv\Scripts\python.exe -m pytest -q` (94 passed) and
`node --test tests/*.test.cjs` (51 passed). DOM fixtures cover current markup,
clipping, row isolation, missing fields, aria counts, zero, reply structure,
deduplication, bounds and comments-only scrolling. HTTP tests execute the actual
JS payload through strict validation and SQLite, including history/idempotence.
No engagement action was performed. No commit was created.
