# Visible VIDEO DETAIL metrics

Current extractor: `tiktok-video-detail-v2`. Legacy v1 payloads and historical
rows remain supported; no database reset/migration is required for this revision.

## Real DOM findings

The initial `strong[data-e2e="like-count"]` and `comment-count` nodes displayed
localized placeholders (`Curtida`, `Comentários`), not counts. Their surrounding
action containers (`like-icon`, `comment-icon`, `share-icon`, `favorite-icon`)
carry role=button and accessible labels. Early share labels already contained a
number while the other labels were still empty. For example:

```html
<div data-e2e="share-icon" role="button"
     aria-label="Compartilhar vídeo&#10;21.4K compartilhamentos">
  <button>...</button><strong data-e2e="share-count">Compartilhar</strong>
</div>
```

In real command #25, after waiting for loading, the same semantic nodes contained
`31.2K` (likes), `1408` (comments), `21.4K` (shares), and `17.5K` (favorites).
Thus a document-ready event plus a nonempty count node is insufficient: placeholder
labels can exist before actual numbers. The old reader returned too early.
The bounded parent/child inspection also found no CSS-generated numbers in the
early label-only snapshot (#23). No global page text or hidden application state
was used to reconstruct missing counts.

## Extraction

`extractVisibleMetric(document, window, field)` is isolated and testable. It uses
dedicated data-e2e count nodes, their own action container, local spans, and
accessible labels on visible elements. The local boundary excludes other metric
controls, page/card containers, descriptions, forms and comment bodies. It never
clicks controls or collects comments. CSS-generated content is supported only
when a visible local element renders a literal numeric string; arbitrary data
attributes are not treated as visible counts.

Priority and confidence are deterministic:

| Method | Confidence | Priority |
|---|---:|---:|
| Dedicated semantic count text | 0.98 | 4 |
| Action-local labelled text | 0.94 | 3 |
| Adjacent local numeric span | 0.90 | 3 |
| Visible literal CSS-generated content | 0.95 | 3 |
| Accessible label/value on the visible local control | 0.95 | 2 |

Conflicting candidates at the same priority are rejected. Counts from a different
metric label are rejected. Literal 0 is valid; an absent count never becomes 0.
Recognized raw numbers are normalized with the shared exact K/M/B parser,
including decimal comma and point. Unknown numeric formats preserve raw evidence
with value=null and confidence=0. Labels without a number stay null; they are
retained separately in the bounded audit snapshot, not used as raw_value.

Every extracted metric carries value, raw_value, source=video_detail, method,
confidence, and server observed_at. Pydantic validates normalization, method and
confidence, preventing labels from being submitted as normalized counts.
Full accessible label text stays in the small sanitized observation snapshot.

## Readiness and navigation

READ_VIDEO_DETAIL navigates only to a known library video. If that video is
already current, it activates the tab without restarting page loading. It brings
that tab's existing Chrome window forward, restores it only if minimized, and
allows one bounded recovery if the document reports hidden. No page interaction
is added. It waits for two matching numeric likes/comments samples, within a
25-second window. A fresh metadata-only read at the deadline can be saved with
null metrics; missing page metadata fails rather than fabricating a capture.
Visible security challenges stop reading and require human intervention.

Failed loads remain FAILED. The sequence helper stops on failure; validation
resumed from the failed position without reloading the same video, preserving
all successful earlier observations. Background/hidden-window rendering and
network timing remain operational limitations; no bypass is used.

## Real validation: 2026-10-21

First validate one video (#25), then the remaining positions. The latest v2
observation for each of the eight videos in search capture `command:9` is:
commands #25, #26, #28, #29, #30, #32, #33, #35. Timeouts #27, #31 and #34
are retained as failures, and were retried only after their terminal state.

| Field | Numeric observations / sample | Coverage |
|---|---:|---:|
| views | 0/8 | 0% |
| likes | 7/8 | 87.5% |
| comments_count | 7/8 | 87.5% |
| shares | 8/8 | 100% |
| favorites | 7/8 | 87.5% |

The >=75% likes/comments target is met without excluding the partial video from
the denominator. Position 5 exposed only a share number during its read:
`79.2K -> 79200`, method=aria_label, confidence=0.95. Its other metrics stayed
null. Other real examples: `31.2K -> 31200`, `83.1K -> 83100`, `156K -> 156000`,
`1408 -> 1408`. Semantic text evidence has confidence=0.98.

No views count node was found in these detail reads. Views stay null in these
observations; views from older search observations are not relabelled as detail
data. The library's best-known fields and search-only coverage remain separate.
Library=12, current capture=8, new=1, updated=7 were preserved. No videos or
historical observations were deleted and no engagement was performed.

The local, read-only validation report is
`.runtime/video-detail-metrics-validation.json`, generated from SQLite rather
than hardcoded dashboard values. It contains each video/command, raw/normalized
counts, source, method, confidence and timestamp.

## Tests and manual reproduction

Run the existing environment's Python tests and `node --test tests/*.test.cjs`.
New coverage includes placeholder labels, adjacent spans, accessible counts,
CSS-rendered values, hidden/offscreen fields, unrelated page numbers, cross-metric
labels, conflicting candidates, zero, unknown formats, K/M/B, delayed counts,
partial timeout, current-video reread, window recovery, challenge refusal, and
the actual JavaScript payload through FastAPI/SQLite with strict provenance.

For a read-only reproduction, use DEV CONTROL automatically:

```
python scripts/devctl.py reload-all
python scripts/read_video_details.py --capture-id command:9 --limit 1
python scripts/read_video_details.py --capture-id command:9 --start-position 2 --limit 7
```

Use the intended current capture ID on a different database. Do not reset the
database. Open the panel to verify stored numeric counts; OPEN only navigates.
This validation does not close the separate, still-failing search-card coverage
gate and does not add profile/comment extraction, AI or new platforms.
