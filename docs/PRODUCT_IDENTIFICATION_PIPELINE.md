# Offline identification and supplier evidence foundation

This foundation performs no network requests. It creates no final Product entity,
identity decision, Gold label, vocabulary approval or supplier match.

## Evidence flow

TEXT EVIDENCE + COMMENT EVIDENCE + VISUAL EVIDENCE + WEB/SUPPLIER EVIDENCE
produce a **Product Identity Hypothesis**, never an automatic truth or merge.

Each source must retain raw text/reference, source entity/ID, observed_at, method,
language where known, and the video/creator to which it actually belongs. Empty
fields remain unknown. Multiple captures of the same caption, comment or listing
are not independent corroboration. A source can contradict another source.

- Text provides explicit names/modifiers; marketing text and query context alone
  do not establish identity. Preserve the original phrase alongside normalization.
- Comments can suggest a name or intent; a question or repeated commenter is not
  a verified identification. The unresolved phrases stay reviewable suggestions.
- VisualProductEvidence already stores assisted references and possible names.
  A future Lens/visual provider must be explicitly invoked, bounded and return
  proposals with image reference, query method, result URL, observed_at and review
  status. A similar image does not establish model/SKU/brand equality. No provider
  runs in this sprint; remote thumbnail references were not fetched.
- Web/supplier listing evidence describes an external offer, whose title/image
  can be inaccurate, stale or copied. Preserve listing provenance separately.

A future identity hypothesis should link evidence IDs, tentative name, observed
attributes, conflicting attributes, missing information and review status. Match
confidence is an explicitly attributed heuristic, not a probability or Gold label.
Promotion to a confirmed identity requires an explicit review policy and independent
support. No transitive merges or automatic Gold updates are introduced here.

## SupplierListingEvidence

The Pydantic contract lives in `app/supplier_foundation.py`; its generated JSON
schema is exported with the offline report. It is a schema only: no table,
ingestion endpoint, scraping connector or database migration.

| Field | Meaning |
|---|---|
| product_entity_id | Nullable future association; no entity is fabricated |
| identity_hypothesis_id | Nullable tentative association, separate from listing |
| provider | Recorded source/provider, not an invoked integration |
| listing_title / listing_url | Raw title and HTTP(S) reference, never fetched |
| price / currency | Nonnegative decimal and explicit ISO-style currency code |
| min_order | Positive integer; null means unknown |
| shipping | Separate price/currency, destination country and textual terms |
| country | ISO-style country code if known; do not infer origin from provider |
| rating / rating_scale | Source-specific rating and declared scale |
| orders | Nonnegative observed count or unknown |
| observed_at | Timezone-aware evidence timestamp |
| match_confidence | Nullable attribution, 0..1; never computed by this contract |
| review_status | unreviewed, reviewed or rejected; reviewed does not confirm identity |

No currency conversion, shipping estimate, current availability, verified seller
status or price recommendation is derived. Even a high match_confidence does not
confirm a Product Identity. One product may have multiple listings; one listing
may contain multiple variants. Neither association merges product hypotheses.

## Offline audit semantics

Unclassified groups A–F are diagnostics with one primary group and overlapping
tags. The fixed precedence is D, E, F, A, C, B. E requires explicit negative
evidence, never merely no candidate. F means a potential coverage gap, not a new
category. No category, taxonomy, classifier or human review is changed by audit.

Audit noun/function cues are a small transparent inspection aid. They are neither
the detector vocabulary nor a universal product detector. Captions not covered by
those cues remain generic/functional for triage, which is not a factual judgement
of their visual content. Existing human product-presence reviews may support
visual scheduling; they never become category classifier inputs or new labels.

Visual HIGH requires candidate missing, likely-product evidence, thumbnail
reference, generic/no caption, insufficient latest comments and unknown/ambiguous
category. MEDIUM requires likely-product evidence plus thumbnail and no candidate.
Other candidate-missing videos stay LOW, including unavailable previews; reasons
show the missing information. Thumbnail availability means a stored reference,
not a fetched, available or visually inspected image. No Lens is run.

Gold FN cause diagnostics overlap. Primary cause is the first applicable:
unknown_vocabulary, no_text, generic_caption, insufficient_text_evidence,
missing_enrichment, likely_visual_dependency, other. Visual dependency is a
possibility inferred from missing text/preview context or an existing review note,
not a new human reason. Human names are not used as detector training data.

Query repeat rate uses search observations: (appearances - distinct videos) /
appearances. Observation uniqueness is distinct videos / appearances. Existing
session-level novelty and known-video duplicate rates remain separately available;
they use different denominators and must not be compared as the same metric.
Unexecuted queries have null performance, not zero quality. Historical ranks
cannot demonstrate superiority when only one query has observations.

The dashboard's new offline panel is text only and makes one local GET request.
It does not fetch thumbnail URLs, link externally, change labels or call any
browser endpoint. Category filters remain inside the existing Videos section.
