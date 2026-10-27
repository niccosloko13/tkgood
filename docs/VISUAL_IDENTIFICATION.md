# Visual Product Identification v1

Local upload, drag/drop, organized assets, FN-first assisted preparation and
current-image comparisons are now described in [LOCAL_VISUAL_ASSETS.md](LOCAL_VISUAL_ASSETS.md).
That additive flow accepts real files without TikTok and preserves this evidence
entity, legacy records, remote thumbnail references and existing review history.

The v1 pipeline records image-bound suggestions and explicit human decisions.
It never confirms a Product Entity, creates a product candidate, modifies Gold
labels, clears security stops or invokes TikTok. Supplier listings remain in
their separate future contract. Product-search evidence is identity context,
not supplier discovery.

## Source and pilot boundaries

`VisualSearchProvider` has separate `vision_model`, `web_image_search` and
`google_lens_assisted` adapters. All currently use **assisted input only**:
they accept an attributable result supplied by a human/operator and report
awaiting_assisted_input when it is absent. No remote model, search or Lens
integration is configured. No undocumented Lens endpoints, scraping, browser
automation or API workaround exists. Provider confidence remains original
metadata; it does not become an identity probability.

The pilot takes the first at most 14 HIGH items, freezes their video IDs and
records each source availability outcome. It never expands to MEDIUM. Available
images can proceed to assisted review. Unavailable images do not invoke a
provider and do not acquire a suggested name from caption, query or Gold labels.

Source priority: explicitly associated local frame, local thumbnail, embedded
persisted PNG/JPEG/WebP thumbnail. Local files must remain inside data/media or
data/visual-images. Resolved paths, file size, image signatures and SHA-256 are
checked. A remote thumbnail reference is not a locally available image; **no
remote images are fetched**, including TikTok CDN and non-TikTok URLs. This
conservative v1 policy avoids expired links, tracking and security-stop bypass.
For legitimate future images, place the actual existing file inside an allowed
folder and explicitly associate it with the correct video. Do not rename an
unrelated file as evidence for that video.

The source resolver does not search browser cache, disk screenshots, arbitrary
directories, cookies or login data. It never fabricates a frame or reconstructs
an image from a caption. The new UI renders only the local image endpoint.

## Evidence, hypotheses and human review

Existing `visual_product_evidence` receives additive source_type, aliases_json,
image_sha256, reason, provider_version and idempotency_key fields. Existing
records and legacy statuses are preserved; old unbound evidence is not silently
promoted into v1 hypotheses. A new suggestion always starts as **suggested**.
Transitions to accepted/rejected/unclear require an explicit human API/UI action
and append visual_review_history. Accepted means accepting a visual proposal,
not a final identity or a Gold label. Repeated submission of the same attributed
proposal/image is idempotent and does not reset a human decision.

Each proposal must refer to the current image hash; a stale image submission is
rejected. Raw possible_product_name is retained. Canonical name suggestion uses
Unicode NFKC, whitespace collapse and casefold only; no stemming, translation,
brand/model inference or cross-product alias merging. Aliases supplied by the
provider are deduplicated as suggestions, never accepted automatically.

Hypothesis evidence links actual visual, caption, comment and web observation
IDs. The original Gold names are not inputs to proposal creation or confidence.
Exact repeated comment observations do not increase confidence. Listing source
snapshots are immutable; changed evidence needs a new observed_at timestamp.
The latest snapshot per URL participates in the hypothesis, so repeat captures
and same-site subdomains do not create extra independent sources.

## Confidence rules

Version 1 is an explicit heuristic, not a probability or existing resolver score:

- 0.25 for an image-bound visual proposal.
- +0.10 for literal non-generic caption name/alias support.
- +0.10 for literal non-generic comment support, regardless of repetition.
- +0.25 only with at least two compatible, title-supported listings on separate
  site buckets **and** separate manually reviewed independence groups.
- Cap at 0.70; generic canonical names and explicit observed contradictions cap
  at 0.20. Rejected proposals have confidence zero. Nothing auto-confirms.

A single result cannot exceed 0.45 even with caption/comments. Site buckets use
a conservative last-label heuristic with common multi-label suffixes; they do
not prove ownership independence. Manual attestation is still required, and
cross-site copied listings remain a risk. Compatibility is explicitly attributed
to the human review, not inferred by the server. Limited literal negation cues
in captions/comments and manually marked listing contradictions reduce support;
absence of such cues does not prove that no contradiction exists.

## Gold comparison

All existing reviewed videos can be compared offline with suggestions. Automated
comparison means **literal normalized name equality only** (including suggested
aliases). A different string is not automatically labelled visual_wrong; a
synonym may still be correct. Helpful/wrong judgements require a separate human
visual_gold_assessment, which never writes gold_video_labels, gold history or
benchmark runs. Non-evaluable denominators return null rates. A name match is
not proof of the correct physical item/model. No recall improvement is claimed
without actual visual suggestions and evaluation.

## Local API / execution

- GET `/api/visual-identification`: HIGH review context, providers and metrics.
- GET `/videos/{id}` and `/videos/{id}/image`: context and validated local image.
- POST `/videos/{id}/image`: relative_path and local_frame/local_thumbnail.
- POST `/videos/{id}/suggestions`: attributed image-bound ProposalInput.
- POST `/evidence/{id}/review`: human_reviewed=true and accepted/rejected/unclear.
- POST `/evidence/{id}/product-search`: title, URL, source, observed_at,
  possible_match, match_reason, compatibility/contradiction and independence.
- POST `/evidence/{id}/gold-comparison`: separate explicit human comparison.

Routes above are relative to `/api/visual-identification`. Provider result URLs
and listing references are recorded, not fetched. After a suggestion exists,
the UI offers an explicit human web search link and a form to preserve the
actual listing evidence; it is not restricted to Lens results. The new panel
has no Gold save action and cannot write supplier listings.

`scripts/visual_identification_report.py --run-pilot` is an explicit local pilot
action. Without that switch, the script exports the latest persisted pilot only.
It records availability, never launches a browser or provider request.
