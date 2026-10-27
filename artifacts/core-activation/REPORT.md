# BABI — Intelligence Core Activation

2026-10-23. Existing workspace and `.venv`. No commit. Zero TikTok access.

## Before and after

| State | Before | After |
|---|---:|---:|
| AUTO | 0 | 0 |
| REVIEW | 0 | 6 |
| UNRESOLVED | 45 | 39 |
| Local assets | 1 | 1 |
| Real image embeddings | 0 | 1 |
| Real text embeddings | 0 | 9 |
| Active FAISS vectors | 0 | 8 |
| Approved Product Entities | 0 | 0 |

The existing core was corrected, not replaced. No production AUTO count was forced. AUTO remains reachable under the text and multisource policies, as verified by isolated regression fixtures; the persisted library currently lacks the independent support required to use it safely.

## Decision-gate changes and text path proof

The previous gate checked image availability before recognizing text evidence. Its `text_supported` flag was derived only from existing visual proposals. Thus a specific caption/candidate could incorrectly become UNRESOLVED_NO_VISUAL.

The existing gate now supports independent paths:

- **Text:** specific caption and candidate can enter REVIEW without an image. AUTO additionally requires recurring candidate observations, specific compatible comments from independent authors, and no conflict.
- **Visual-dependent:** generic caption/local image enters the existing assisted visual flow and local OpenCLIP/retrieval cross-check. Missing provider evidence remains explicit.
- **Insufficient:** generic text without useful evidence remains UNRESOLVED.

Specificity combines the existing signature/head vocabulary, compound structure, specific modifiers, literal caption support, unique comment support and candidate recurrence. It is not a list of allowed full product names. Generic heads such as cleaner/device/tool remain generic. A qualified compound such as mini vacuum cleaner is handled differently. Explicit identity negations cannot count as compatible positive comments or trigger text AUTO. Product complaints are a separate dimension and do not automatically contradict identity.

### Video 3

Persisted caption: **Soap dispenser and dish brush in one**.
Existing candidates: **Soap dispenser**, **dish brush**.

Result: **REVIEW / REVIEW_TEXT_COMPOSITE_PRODUCT**. The caption describes a combined product while candidates name two components. No image is required, and no Gold label was read to reach the decision.

### Video 1

Caption remains generic: **Easy to remove the stains #gadgets**. Existing unresolved phrases and real comments include **vacuum cleaner** and **Mini Vacuum Cleaner Price? very useful**.

Result: **REVIEW / REVIEW_SPECIFIC_COMMENT_HYPOTHESIS**, probable name **Mini Vacuum Cleaner**. `generic_text=false`, `text_supported=true`; literal caption support is still false. This is a specific observed comment hypothesis, not an accepted product or visual identification. Unresolved phrases and candidates were not modified.

## Targeted pilot and visual path proof

Pilot IDs: **1, 3, 9, 10, 13**. The additional three text examples came from persisted caption/candidate specificity, not Gold selection. Their names include Burger Patty Maker, fruit spinner and long-handled floor brush. The pilot completed before the 45-item lightweight run.

Only **one** valid local image exists, attached to video 1. No additional three image-bearing videos were available; that pilot expansion is **blocked_by_missing_local_assets**. No remote thumbnail or TikTok CDN fallback was used.

The actual path exercised was local asset -> real OpenCLIP image embedding -> typed FAISS top-3 -> persisted retrieval evidence -> conservative decision. The existing Lens/visual evidence providers remain available in assisted mode. **LENS_ASSISTED_REQUIRED** accurately records that Lens has not run. No visual product proposal, web confirmation, supplier request or remote visual-provider invocation was fabricated.

## Real OpenCLIP inference and cache

Original proof: [first-pilot.json](first-pilot.json). Final repeated run: [pilot.json](pilot.json).

| Field | Observed result |
|---|---|
| video_id / asset_id | 1 / 1 |
| Asset SHA-256 | e1695b03fa73573443487a0ae0ae56547a5ed5dc11a71c37e96088a8313e8e09 |
| Model | OpenCLIP 3.3.0, ViT-B-32, laion2b_s34b_b79k, fp32 |
| Device | CPU |
| Runtime probe | CUDA_RUNTIME_UNAVAILABLE; no CUDA capability was assumed |
| Cold duration | 12,610 ms, including imports/model loading/preprocessing/inference |
| Embedding dimension | 512 |
| First cache status | miss |
| Model loaded during inference | true |
| Second execution | hit, identical vector, no recomputation |
| Later worker processes | persisted cache hits |
| Completion lifecycle | model explicitly unloaded; backend startup remains unloaded |

The checkpoint SHA-256 is `1bd3c7172de5b207ceac554f5ab5266166f3b9baccc9af5989bc801016d080ad`. Runtime only reads this verified local checkpoint. No weights were downloaded during activation.

Loading follows the [official PyTorch mmap/meta/assign recipe](https://docs.pytorch.org/tutorials/recipes/recipes/module_load_state_dict_tips.html): construct the architecture without resident initial weights, map the pinned checkpoint and strictly assign all state. The constructor's “initialized randomly” warning occurs before strict assignment; no inference is allowed before assignment succeeds. This avoids a duplicate resident copy of the checkpoint. Final vectors are real model outputs, not generated test vectors.

Cache namespace includes model/package/weights/checkpoint version, modality and input SHA. Image keys use the original validated asset bytes. The database contains **1 image + 9 text embeddings**; the index uses the eight candidate-name vectors, while the extra text embedding is persisted caption context.

## Resource governor, GPU awareness and resume

The former global 85% RAM / 2500 MiB rule could permanently prevent useful local work. The existing governor now reports **RUN / WAIT / DEFER / STOP** and distinguishes cold mmap-load and warm-inference admission.

- Cold available-memory budget: **1024 MiB**; warm inference: **384 MiB**.
- Critical STOP: available memory below **256 MiB** or RAM at least **98.5%**.
- CPU admission below **85%**, two Torch CPU threads, single worker, batch one.
- Pressure invokes a **20-second cooldown**; resource waits do not exhaust actual transient-error attempts or become permanent failures.
- Runtime GPU detection requires a usable CUDA runtime, free memory and a small allocation/synchronization probe. Failure falls back to CPU or defers. The installed runtime is CPU-only.
- Idle unload is configurable, currently **30 seconds**. Early timer wakeups are rescheduled. The first full regression found this timer edge case; it was fixed without relaxing the test.

During the earlier controlled admission check, RAM pressure reached **95.7%, 684 MiB available**, and inference was deferred. The successful cold worker recorded **90.7% RAM, 1492 MiB available, CPU 14.3%**, allowing the smaller mmap-backed incremental budget. These are observed resource samples, not a measured process peak. Full resource samples are in the pilot artifacts.

The existing fixed-task launcher now has `intelligence-worker`. Worker lifetime is file-locked, and the backend returns a task ID instead of loading the model or blocking while waiting. The worker resumes after cooldown within its bounded **180-second** run; if the deadline expires it leaves a resumable deferred checkpoint. It is not an unlimited retry service. Actual backend checks report `model_loaded=false` and OpenCLIP `ready` from the persisted inference/cache state.

## FAISS corpus, atomic rebuild and retrieval examples

The existing index supports separate reference kinds and modalities:

| Reference kind | Vectors | Authority |
|---|---:|---|
| PRODUCT_ENTITY | 0 | Approved identity only |
| CONFIRMED_OCCURRENCE | 0 | Approved observation, still provenance-bound |
| CANDIDATE_REFERENCE | 8 | Retrieval reference only; product_id is null |

Every result includes reference kind, source, similarity, model version and generation. Candidate references cannot authorize an entity, identity match or merge even at similarity 1.0. Entity/occurrence references for the same product are not counted as competing independent products.

Rebuild remains temporary build -> validate dimension/count -> metadata/checksum -> atomic pointer swap. Old generations remain on disk. Unchanged corpus/model reuses its generation. Existing corruption/version/failed-swap tests remain in the suite. See `verification.json` for the full active generation and model version.

Actual video 1 image top-3:

| Reference | Cosine similarity | Kind | Source |
|---|---:|---|---|
| Soap dispenser | 0.273133 | CANDIDATE_REFERENCE | candidate:1 |
| Portable Dryer | 0.270813 | CANDIDATE_REFERENCE | candidate:7 |
| 3 in 1 Window Cleaner | 0.270282 | CANDIDATE_REFERENCE | candidate:6 |

These weak neighbours do **not** identify video 1. In particular, the comment's vacuum-cleaner hypothesis is absent from the candidate corpus. Similarity is not probability, and no retrieval result was promoted into a Product Entity. Product identity still needs visual/Lens/web corroboration or an explicit justified human review.

## Purchase Intent and identity-independent dimensions

The existing comments module now produces deduplicated lexical observations for where-to-buy, link request, price question, want/need and purchase statements. Consumer classes separate PURCHASE_INTENT, POSITIVE_REACTION, NEGATIVE_REACTION, QUESTION, PRODUCT_COMPLAINT and QUALITY_COMPLAINT, retaining comment evidence IDs.

Repeated captures, normalized punctuation/case variants and anonymous copies do not inflate independent comment counts. Identical short text from different authors is conservatively collapsed for the comment denominator; real unique authors are reported separately. These are lexical purchase-interest signals, not verified demand, buyers or conversion rates.

**Video 1:** 60 raw observations -> **30 unique usable texts**, **22 purchase-intent comments**, intent ratio **0.733333**, **26 known authors**, status **measured**, strength **STRONG**. Examples include “onde compro um desses?”, “eu quero”, “link pls”, “Mini Vacuum Cleaner Price?” and “Need”. Full original text and IDs remain in `verification.json`/decision snapshots.

**Video 18:** Identity **UNRESOLVED**, Purchase Intent **STRONG**, measured on **19 unique texts**. This is an actual persisted example, not a test fixture. Six library items have measured purchase-intent samples: videos **1, 3, 6, 12, 18, 39**.

Signal Quality, Consumer Reaction, Product Quality signals and Commercial readiness use their own evidence. Complaints are lexical partial quality evidence; absence of complaints is not a zero quality score. Viral Potential and Trend remain insufficient_data/insufficient_history when time-series evidence is inadequate. No final Opportunity/Gold score was added.

## Gold evaluation — downstream only

Gold was read only after the production pilot/library run and was not mutated. Fifteen reviews exist: **14 positive, 0 negative and 1 unclear**. Thirteen positive rows have a name suitable for literal-name comparison.

| Metric | Value | Denominator / limitation |
|---|---:|---|
| Presence-hypothesis precision | 1.0 | 6 TP, 0 FP; **no reviewed negative examples**, so not evidence of general precision |
| Presence-hypothesis recall | 0.428571 | 6 TP / 14 positive reviews; 8 FN |
| Retrieval top-1 name accuracy | 0.0 | One actually queried Gold video; literal reference-name agreement |
| Retrieval top-3 name recall | 0.0 | Same one queried video; true name absent from corpus |
| Hypothesis top-1 literal agreement | 0.166667 | 1 / 6 supplied names |
| Hypothesis top-3 literal recall | 0.153846 | 2 / 13 named positives |
| AUTO accuracy | null | 0 production AUTO decisions |
| False-merge rate | null | No adjudicated same-product pair set |
| REVIEW rate | 0.133333 | 6 / 45 |
| UNRESOLVED rate | 0.866667 | 39 / 45 |

Presence-hypothesis precision/recall measure named AUTO/REVIEW proposals, not final physical-product identity. Literal-name diagnostics do not infer synonyms or create human labels. No entity or association was created, so there were **0 merge actions**; this is not a measured 0% false-merge rate. See evaluation definitions and per-video comparisons in `verification.json`.

## Tests and preservation

**Final complete suites: 364 Python passed, 121 Node/dashboard passed, zero failures or skipped tests.** Seven Python deprecation warnings remain (FastAPI/websocket and FAISS SWIG wrappers). The final Python task is `c2423404cf7e446bbd75b18369acfe90`; final Node task is `9f9e98dfab3d4bd5a80b450c5b55142b`. Existing coverage was not removed or weakened.

The existing tests remain. New regressions cover video 3 text-only composition, video 1 specificity, optional visual evidence, reachable text AUTO, negative identity comments, generic heads/novel compound structure, resource defer/resume without retry exhaustion, GPU allocation fallback, idle unload, typed corpus bootstrap, candidate-reference safety, purchase-intent dedupe, identity-independent dimensions and Gold/security isolation. The earlier timer failure is retained in local logs; the final result is recorded in `test-results.json`.

Checkpoint: [checkpoint.db](checkpoint.db). Read-only preservation export: [verification.json](verification.json).

**55 pre-existing source tables are identical** to the checkpoint. Gold, candidates, unresolved phrases, visual assets/evidence, classifier/category outputs, query/enrichment history and resolver evidence remain unchanged. All original decision records and event rows remain present. Queue state changes/supersession and new decisions/retrieval/cache rows are intentional and retain history. The exact security-stop and incident-history records are unchanged.

No TikTok navigation, CDN requests, discovery, engagement, browser automation, login/cookie/profile changes, Lens scraping, supplier scraping, security-stop clearing or commit occurred. The activation worker denies all socket connections. Only the owned backend was restarted with devctl; Chrome/Companion were not reloaded.

## Files changed and remaining blockers

Reused/extended: existing gate/core/jobs/embedding/index/evaluation/API modules, existing comments module, core dashboard and fixed background runner. Added: `config/consumer_signals.json`, bounded `scripts/core_activation.py`, read-only `scripts/report_core_activation.py`, activation regressions and artifacts. No alternate Core, resolver, visual entity, taxonomy or detector was rebuilt.

Remaining blockers are data/evaluation limits, not an empty runtime: only one local image, no actual Lens/web identity evidence, a small candidate-only retrieval corpus without the vacuum-cleaner target, no reviewed negative/pair-labelled evaluation set and no production AUTO cases meeting policy. Add real local assets and assisted visual evidence before expanding identity claims. Do not unblock TikTok or fabricate entities to fill the corpus.
