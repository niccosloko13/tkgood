# BABI — Visual Identity Completion V1

2026-10-23. Existing workspace / `.venv`. No commit. Zero TikTok access.

## Outcome

The existing visual pipeline now operates on a real local asset without asking the user for a product name, provider, SHA or manual confidence. It performs image-only automatic analysis, hypothesis normalization, cached OpenCLIP/FAISS cross-check, persisted-context cross-check, bounded cited web search and the existing Decision Gate.

**Available assets: 1. Processed assets: 1.** The active probable product is **Window vacuum cleaner**; **Glass cleaner device** remains an alternative. The decision is **REVIEW / REVIEW_CONFLICTING_VISUAL_RESULTS**, not a confirmed identity. The original image-only preflight proposed **Electric Window Cleaner**. All provider responses and prior decisions remain in history.

| Identity state | Before | After |
|---|---:|---:|
| AUTO | 0 | 0 |
| REVIEW | 6 | 6 |
| UNRESOLVED | 39 | 39 |

No AUTO count or Product Entity was forced. End-to-end operation is proven; general precision and the condition that visual review becomes exceptional are **not demonstrated by one ambiguous image**. The visual sample has one REVIEW out of one processed asset; the whole library remains 6/45 REVIEW.

## Reuse and changes

Reused Visual Assets, VisualProductEvidence, visual pilot/history tables, Product Candidates, Identity Resolver, OpenCLIP adapter/cache/governor, FAISS, Decision Gate, Gold Set and Product Entity approval boundary. **Decision Gate code/thresholds were not changed.** Category taxonomy, detector, resolver and supplier foundation were not rebuilt.

Provider results, text cross-check and multimodal provenance are additive JSON fields on existing visual evidence. Existing visual pilot rows hold resumable stage/context snapshots and input fingerprints. Existing web evidence now also records product name, compatibility and independence basis. Existing job queues gained a bounded `visual_identity` work type; browser/content queues remain untouched.

`app/visual_providers.py` implements the existing VisualSearchProvider interface. The fixed `visual-identity-worker` uses the existing background runner and shares the existing heavy-worker lifetime lock. No parallel Core or alternative identity store was introduced.

## Actual visual provider and Lens states

| Provider | State | Actual activity |
|---|---|---|
| Configured vision model | AVAILABLE_AUTOMATIC | Real image-only API inference via the configured OpenRouter endpoint, model `openai/gpt-4.1-mini` |
| Google Lens assisted | AVAILABLE_ASSISTED | LENS_ASSISTED_REQUIRED; operator may submit the local image manually |
| Google Lens automatic | UNAVAILABLE | Not executed or simulated |

The configured credential/endpoint were reused, without exposing the key or sending it to a different issuer. The client accepts only the supported HTTPS API hosts/paths, refuses redirects and makes no automatic request retry. A 403 blocks that visual run/job and stops further provider work. Missing credentials or provider failures are explicit unavailable states.

The alternate provider is **vision-model image analysis**, not Google Lens or a claimed reverse-image-search result. It receives the image as a base64 data URI and an image-analysis instruction. **No caption, comments, existing name, unresolved phrase, creator, query, category or Gold label enters that first prompt.** Names are generated from the image before text/web cross-checking. No image was generated, invented, downloaded from TikTok or altered to manufacture details.

## Context, hypotheses and normalization

Before inference the application gathers persisted caption, hashtags, comments, creator, query source, candidates, unresolved phrases, category/product family and Purchase Intent. This snapshot is used after image analysis; it does not force the visual answer.

The original image-only preflight returned one specific type, Electric Window Cleaner, with naming alternatives Cordless Window Cleaner and Handheld Window Vacuum Cleaner. A subsequent automatic worker analysis returned two plausible types, Window vacuum cleaner and Glass cleaner device, with their observed aliases. There are **3 stored historical hypothesis rows and 2 active hypotheses**.

Same-provider reruns are not independent votes. Only the active response for a provider/model enters the core, preserving the provider's hypothesis order; accepted human evidence is not overwritten. Earlier responses remain available in history. This also corrected an insertion-order issue that could put the last inserted alternative ahead of the provider's first hypothesis.

Normalization merges explicit name/alias equivalence and removes normalized duplicates. It does not merge different products merely because they share a generic head or an embedding similarity. Canonical suggestions remain observed provider names, not invented blended names or Product Entities.

Text cross-check for the real asset is **NEUTRAL**: the generic stain-removal caption and broad vacuum-cleaner comments cannot confirm or refute the specific window-cleaner type. The existing Home/Cleaning category is coarse supporting context, not identity truth. Explicit disjoint specific candidates or identity negation produce CONFLICT; compatible literals produce SUPPORTED. No Gold labels are consulted in this path.

## OpenCLIP and FAISS

The existing image embedding was reused: asset 1, SHA-256 `e1695b03fa73573443487a0ae0ae56547a5ed5dc11a71c37e96088a8313e8e09`, 512 dimensions, OpenCLIP 3.3.0 / ViT-B-32 / laion2b_s34b_b79k / fp32. The recorded image path is a **cache hit**, not a re-created vector. New hypothesis-name embeddings were computed locally and persisted; the database now has **1 image and 12 text embeddings**.

The original Electric Window Cleaner hypothesis had image/text cosine **0.304960**. Actual active-hypothesis cross-checks and model versions are stored in each proposal's `multimodal_json` and in [verification.json](verification.json). Cosine is not a probability or identity confirmation.

FAISS still contains **8 CANDIDATE_REFERENCE vectors**, 0 Product Entities and 0 Confirmed Occurrences. Its existing atomic rebuild/version/checksum protections were preserved. Visual hypotheses were not silently converted into indexed final products or candidates.

Actual image top-3 remains:

| Reference | Kind | Cosine |
|---|---|---:|
| Soap dispenser | CANDIDATE_REFERENCE | 0.273133 |
| Portable Dryer | CANDIDATE_REFERENCE | 0.270813 |
| 3 in 1 Window Cleaner | CANDIDATE_REFERENCE | 0.270282 |

These weak neighbours are cross-check references, not identity votes. Even a candidate-reference cosine of 1.0 cannot create an Entity; this remains a regression test. No destructive merge or identity association was performed.

## Web confirmations

After visual names exist, the provider searches a small configured allowlist of public manufacturer domains. The server-side Exa search is bounded to one search / at most three results; it cannot select TikTok/CDN domains. The application does not scrape product pages, follow arbitrary returned URLs, search prices or select suppliers.

Only URLs present in actual returned citations and on the allowlist are stored. One development response was plain cited text rather than schema JSON; the adapter now performs a separate structured extraction, without another web search or invented URLs. An uncited or out-of-domain URL is discarded.

The active run has **2 distinct cited pages**, from **2 publisher domains**:

- [Kärcher Window Vac family](https://www.kaercher.com/int/home-garden/window-vacs.html).
- [Bosch window vacuums](https://www.bosch-diy.com/gb/en/cleaning-tools/window-vacuums).

The initial preflight also observed a Kärcher WV 2 Plus page. Historical snapshots remain; there are 7 stored web-evidence rows across hypotheses/runs, **not 7 independent confirmations**.

These pages support the **product family**, not the exact device, brand, SKU or variant. Distinct publisher domains are recorded as an independence clue only. `independence_reviewed=false` and `visual_compatible=false` are intentionally retained: no human inspection or exact listing-image verification was fabricated. This is why web evidence does not automatically promote the suggestion to AUTO.

## Evidence fusion and user flow

The existing gate receives text evidence, image-provider output, Lens evidence if supplied, OpenCLIP/typed retrieval, web observations and conflicts, with separate source IDs. No new unified confidence/viral score was introduced.

The core dashboard now shows Visual Identity counts, image, context, hypothesis/alternative, source evidence and state. Normal operation is **Identificar imagens disponíveis / Analisar imagem**. It launches the bounded worker without requiring a product-name input. Lens remains an explicitly separate assisted image flow; it is never described as executed automatically.

Adicionar imagem appears only when no usable asset exists. Replacing an existing asset remains possible under technical details, preserving the prior upload tests. The existing `persist_visual_asset(video_id, bytes, source_metadata)` contract is reused; future_capture remains blocked by the active security stop. No TikTok acquisition was implemented.

The NEEDS_VISUAL queue currently has **44** source gaps. REVIEW without visual evidence is prioritized first; user-provided historical IDs 4, 5, 6, 11, 12, 14 receive historical scheduling priority only once a local asset exists. No Gold label/name is passed to the provider or gate, and no missing asset triggers a remote thumbnail download. All six historical priorities still lack a local asset.

## Independent intelligence and visual quality

Purchase Intent, Consumer Signals, Category and readiness dimensions continue even while visual identity is pending. Existing measured Purchase Intent remains available on six videos. Video 18 remains UNRESOLVED in identity with STRONG purchase interest.

The provider persisted seven separate visual-quality observations with source reasons:

| Feature | Initial image-only observation |
|---|---|
| demonstration_visibility | observed: handheld contact with a surface is visible |
| problem_solution_clarity | partial: intended cleaning function inferred, mechanism uncertain |
| before_after_possible | insufficient |
| transformation_strength | insufficient |
| visual_novelty | insufficient |
| product_visibility | observed |
| creative_repeatability_possible | insufficient |

These describe a single frame. They do not establish temporal transformation, market novelty, repeatability or a final Viral Score. Later provider observations are retained with their own response provenance, rather than silently overwriting the original interpretation.

## Resource usage and performance

The automatic vision provider is remote; no additional local VLM or model download was required. OpenCLIP remains lazy, cached, governed, batch one, single heavy worker, CPU fallback and idle unload as implemented in activation. The visual worker unloads the local model on completion. Backend startup remains model-unloaded; the API returns a background task ID and does not block on inference or resource waits.

Local pressure defers the existing job without exhausting transient-error retries and resumes after cooldown within the bounded worker. API calls have a finite timeout, no retry loop and bounded output/results. Current resource samples, embedding/cache details and raw provider usage are in the artifacts. No process RSS peak or pure inference latency was measured in this sprint; a cache hit's zero compute time is not claimed as zero HTTP latency.

## Evaluation — after production inference only

The cohort is **one named Gold item with a current local visual result**. The same cohort is used for the three ablations. Matching is strict normalized literal naming, including declared visual aliases; it is not physical SKU adjudication.

| Ablation | Top-1 name agreement | Top-3 name recall |
|---|---:|---:|
| Text-only | 0/1 | 1/1 |
| Visual-only | 0/1 | 0/1 |
| Multimodal | 0/1 | 0/1 |

The new visual names differ from the historical human name. This mismatch is recorded, **not used to relabel Gold or to manufacture a false-identity verdict**. False identity rate and REVIEW physical-identity accuracy are null pending human adjudication. AUTO accuracy is null because AUTO count is zero. UNRESOLVED recovery is **0/39**; the one processed visual item was already REVIEW before this sprint.

The new names are generated automatically, but these results do not demonstrate improved accuracy or exceptional review frequency. More real local assets and adjudicated visual cases are needed before making those claims.

## Tests, preservation and remaining blockers

**Final complete suites: 380 Python passed + 122 Node/dashboard passed; zero failures or skipped tests.** Seven existing Python deprecation warnings remain. Python task: `4bfaff16601a41778530064f815143db`; Node task: `b77ba0d9ca3540588b9595bc030d86c1`.

Final regression totals and task IDs are recorded in `test-results.json`. Existing suites were preserved. New tests cover unavailable providers, Lens state, normalization, cached cross-check, web citation grounding, text support/conflict, Gold isolation, candidate-reference safety, idempotent/deferred stages, current-asset binding, 403 no-retry, same-provider source selection/order and the name-free UI path/upload fallback.

Checkpoint: [checkpoint.db](checkpoint.db). Read-only verification: [verification.json](verification.json). The original Gold, candidates, unresolved phrases, assets, category outputs, query/enrichment history and identity-resolver data are unchanged. Original decision/event records remain present. New visual/web observations and derived decisions are additive. Exact security-stop/history rows are unchanged. No Product Entity, human label or review acceptance was created automatically.

Remaining blockers: only one small local image; no legitimate automatic Lens integration; exact mechanism/brand/SKU remains uncertain; web results corroborate related families rather than the exact object; the FAISS corpus is still small; visual physical-identity accuracy and review-exception frequency cannot be established on this sample. Provider failures/poor images may validly remain UNRESOLVED. No false product is forced to satisfy the success criteria.

Zero TikTok navigation/CDN download, engagement, browser automation, cookies/profile changes, security clearing, stealth, supplier scraping or commit. Only the owned backend was restarted through devctl. Credentials are not present in reports.

## Implementation references

[OpenAI image inputs](https://developers.openai.com/api/docs/guides/images-vision), [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [configured gateway structured output contract](https://openrouter.ai/docs/guides/features/structured-outputs), [bounded domain-filtered web-search tool](https://openrouter.ai/docs/guides/features/server-tools/web-search).
