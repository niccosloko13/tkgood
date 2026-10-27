# BABI — Intelligence Core Consolidation

Date: 2026-10-23. Offline only. No commit.

## Outcome and success criteria

Core implemented and exercised on all 45 persisted videos. **This sprint does not yet meet all success conditions.** Real multimodal same-product retrieval and a reduction in REVIEW with preserved precision remain unproven: only one local image exists, no visual or web proposals exist, and the resource governor refused model inference. No thresholds were relaxed to manufacture success.

Current decisions: **AUTO 0 / REVIEW 0 / UNRESOLVED 45**. Of these, 44 lack a local image and one has a local image but no usable product-name evidence. This is an evidence-routing result, not an improvement in detection recall or precision. Candidates remain candidates.

## Existing architecture audit

The audit was performed before source edits. See [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md) for the complete component/purpose/keep/refactor/merge/remove/reason table. A database checkpoint and original-table column fingerprints were created first: `checkpoint.db`, `before.json`.

### Reused / kept

- Existing candidate detector, candidate evidence, unresolved phrases and provenance-bound identity resolver/signatures.
- VisualProductEvidence, local asset validation/storage, current-image SHA binding, review history, assisted Lens and immutable web snapshots.
- Category taxonomy/classifier, human category review, query metrics/planner and enrichment priorities.
- Gold Set and benchmark as downstream evaluation only. Production input loader was tested with SQLite denying all Gold reads.
- SupplierListingEvidence remains separate from approved Product Entities; no supplier collection.
- Security latch/history, event logging, browser/development command ownership and existing bounded capture queues.

### Merged / migrated callers

- The old category provider stub is a deprecated compatibility shim delegating to the existing canonical visual provider.
- Upload, visual suggestion/review and web-evidence write endpoints now call one lightweight core decision handler in their transaction. They do not load a model.
- Production local image preparation is independent of Gold pilot membership and requires no product-name input.
- The operational identity review path is `/intelligence-core`; it exposes only REVIEW decisions for human identity confirmation. Existing Gold review remains an evaluation tool, not the production queue.

### Deprecated / removed

Deprecated: legacy `browser.py`, `safe_actions.py`, category provider stub and visual proposal confidence as an operational gate. Old confidence remains API-compatible diagnostic output; the core consumes its factual support/provenance fields, never the numeric score. The legacy provider form is folded into technical details.

**Removed: none.** No compatibility module was deleted before migrating its remaining callers/tests. Browser queues were deliberately kept separate from local inference jobs because their security/ownership contracts differ.

## New modules and responsibility

| Module | Why no equivalent was reused |
|---|---|
| `app/intelligence_decisions.py` | One central policy for official states and same-product outcomes; existing resolver remains lexical evidence provider |
| `app/intelligence_core.py` | Coordinates existing observations/evidence, preserves decision/matching history, approves entities only through the gate or explicit review |
| `app/intelligence_jobs.py` | Local idempotent inference work with leases; existing browser/enrichment queues are not local model workers |
| `app/intelligence_embeddings.py` | Previously no local embedding/cache/resource governor |
| `app/intelligence_index.py` | Previously no approved-product FAISS index or atomic generation pointer |
| `app/intelligence_evaluation.py` | Isolated read-only evaluation; no labels passed into production |
| `app/intelligence_api.py` | Thin local API and operational review page |

Configuration is centralized in `config/intelligence_core.json`. Existing resolver-specific lexical policy remains in its existing configuration; taxonomy/detector thresholds were not modified.

## Decision gate and entity boundary

AUTO requires a specific current-image visual suggestion, literal caption/comment support, two attested independent compatible listing sources, and absence of conflicts. A single visual result, a candidate or a cosine score cannot approve an entity. Missing/stale retrieval coverage for existing entities defers otherwise-supported decisions to REVIEW.

Reason codes include AUTO_STRONG_MULTISOURCE_MATCH, REVIEW_CONFLICTING_VISUAL_RESULTS, REVIEW_POSSIBLE_VARIANT, REVIEW_INSUFFICIENT_CORROBORATION, REVIEW_RETRIEVAL_UNAVAILABLE, UNRESOLVED_NO_VISUAL, UNRESOLVED_GENERIC_TEXT and UNRESOLVED_INSUFFICIENT_EVIDENCE.

Same-product outcomes are `same_product_likely`, `possible_same_product`, `different_product`, `insufficient`. The resolver's source-bound lexical evidence, brand/model-like features, negative variant evidence, image/text cosine and independent listings are combined. Weak similarity creates neither an identity nor an unnecessary review task. Retrieved approved identities can be explicitly selected by a human; no destructive merge occurs.

Entity creation requires AUTO or explicit human confirmation of the latest unchanged REVIEW. Prior decision/review/match revisions are retained. No Candidate, Product Entity or Gold label is silently rewritten.

## Queue behavior

Local job types: identity, embedding, index_rebuild. Input fingerprint + job type + target deduplicate work. Heavy and light lanes are isolated. Exclusive lease tokens prevent stale owners from completing work; interrupted leases are recoverable with bounded attempts. New input/policy revisions supersede queued obsolete work while retaining history.

TRANSIENT: at most 3 attempts, backoff. PERMANENT: dead-letter. INSUFFICIENT_DATA: terminal unresolved until new evidence. SECURITY_BLOCK: terminal blocked, **zero automatic retry**. Resource refusal pauses a heavy batch after the first refused item. There is no background timer/browser retry loop; continuation uses explicit bounded local runs.

`blocked_jobs` includes type, target, reason, attempts, last error/attempt and recoverability. Empty blocked/dead-letter lists in production do not mean those branches were untested: isolation, bounded retries and security no-retry were verified in temporary test databases.

Historical job counts and latest per-video decisions have different denominators. An early intermediate candidate-only conflict was corrected before delivery; its archived review/job records remain in history and do not enter the current REVIEW queue. Initial resource refusals are retained, not erased.

## OpenCLIP results

CPU-only OpenCLIP 3.3.0 / torch 2.8.0+cpu / torchvision 0.23.0+cpu. Model ViT-B-32, weights laion2b_s34b_b79k. Official checkpoint revision `1a25a446712ba5ee05982a381eed697ef9b435cf`; SHA-256 `1bd3c7172de5b207ceac554f5ab5266166f3b9baccc9af5989bc801016d080ad`, verified before atomic local publish.

Image/text embeddings are lazy, normalized, separately hashed and cached by model/package/weights/checkpoint version. Runtime uses a local verified checkpoint only; it does not download weights. The explicit install script contacts the official model repository only. No model loads at backend startup.

**Real image embeddings: 0. Real text embeddings: 0. Cache hits: 0.** Model inference was refused by resource policy. Observed pressure included 91.9% RAM / 1302 MiB available; a later observation was 85.0% / 2418 MiB. Limits remain RAM <85%, available >=2500 MiB, CPU <85%, CPU concurrency 1, threads 2. No GPU workload or process termination was used. Model/cache adapter behavior is covered by controlled tests; that is not reported as a real inference result.

## FAISS results and atomic rebuild

FAISS CPU 1.13.2. Only approved Entities enter the index, using the approved image snapshot or approved canonical-name text if that image is unavailable/changed. The modality is recorded; text-to-image retrieval is not mislabeled as image-to-image corroboration.

Current production index is valid and empty: 0 approved products, dimension 512. Rebuilding identical sources/version reuses the generation. No candidate or Gold row was inserted as a fake product.

New generations are built in a temporary directory, validated, paired with checksum/mapping/version metadata, flushed and published through one atomic pointer replacement. Readers verify the checksum before deserializing and keep their generation snapshot. Tests simulated validation failure and failed pointer publication; the prior index remained searchable. Top-3 ordering/version mismatch/corruption checks passed on isolated synthetic test vectors, not production products.

**Real retrieved products/matches: 0.** Multimodal matching on actual products remains unvalidated.

## Product, quality, trend and assisted UX

Primary operational view: probable product, official state, reason, main evidence counts, category, trend availability and separate quality dimensions. Technical payloads/provider/version/IDs live under Details. No manual confidence is required in the core flow, and identification preparation precedes any result-name entry.

Lens remains assisted: download the local image, open Lens manually and register the observed result through the existing evidence endpoint. All results stay suggested. Web confirmations remain immutable evidence snapshots, separate from supplier listings. No Lens/provider call or search was performed during this sprint.

Identity confidence, signal quality, viral potential, product quality, saturation and commercial readiness remain distinct. Missing measures remain null/insufficient_data. Temporal foundations use actual observation dates, distinct creators, deduplicated comments, lexical purchase intent and persisted detail-observation counts. They do not reconstruct publication dates or daily engagement histories. BERTopic/River/ruptures are placeholders with insufficient_history, not heavy integrations.

## Gold evaluation

Gold labels are unchanged and read only downstream. Fifteen reviewed rows exist; 13 positive rows have an evaluable human name. Exact normalized literal-name agreement is deliberately distinct from physical same-product accuracy. No synonyms or new human labels were invented.

Requested retrieval top_1_accuracy and top_3_recall: **null**, because no actual product retrieval/labelled-entity evaluation is available. False_merge_rate: **null**, because there are no adjudicated entity-pair labels. AUTO decision accuracy: **null**, AUTO denominator 0. Current review_rate 0.0; unresolved_rate 1.0.

Separate persisted-text naming diagnostic: top-1 exact name agreement 1/5 suggestions = 0.20; top-3 named-positive recall 1/13 = 0.076923. These are strict literal diagnostics of existing candidates, **not OpenCLIP/FAISS quality or a demonstrated improvement**. See `verification.json` for per-video comparisons and explicit denominators.

False merges observed through newly created links: none; there were 0 entities and 0 identity associations. This is not evidence of a measured 0% false-merge rate.

## Safety and preservation

ZERO TikTok navigation, CDN downloads, discovery, comments/profile calls, engagement, cookie/login/profile changes, Chrome automation, stealth, supplier scraping or security-stop clearing. The only network activity added was package/official checkpoint installation; operational validation requests were to the local backend.

The original-column fingerprints of every pre-existing table matched except `events` and `system_state` (backend startup/heartbeat state). The exact `browser_security_stop` and `browser_security_history` records matched the checkpoint. Gold, candidates, all pre-existing evidence, resolver pairs, taxonomy classifications, query/enrichment/history tables were preserved. See `verification.json`.

Backend restart used `scripts/devctl.py restart-backend` only. Chrome/Companion were not reloaded. No commit.

## Files changed in this sprint

Added: seven `app/intelligence_*.py` modules; `config/intelligence_core.json`; `requirements-intelligence.txt`; three offline scripts (`intelligence_core.py`, `install_intelligence_model.py`, `report_intelligence_core.py`); `app/static/intelligence-core.html`, `intelligence-core.js`; `docs/INTELLIGENCE_CORE.md`; Python/Node core tests; this artifact directory.

Extended: `app/db.py` (additive migration), `app/main.py` (router), `app/visual_identification.py` (production preparation/legacy documentation), `app/visual_identification_api.py` (one core handler at evidence writes), `app/category_intelligence.py` (compatibility delegation), `app/static/index.html` (core link), `app/static/visual-identification.js` (technical fold), `requirements.txt` (psutil), legacy browser/safe-actions documentation, `docs/NEXT_SESSION.md` checkpoint.

The workspace already contained extensive uncommitted prior sprint changes. This list describes this sprint; a repository-wide git diff is not attributed wholesale to it.

## Tests

Complete Python suite: 338 passed. Complete Node/dashboard suite: 120 passed, 0 failures. New core coverage: 36 Python and 2 Node tests. Existing tests were retained, including category, runner/security stop, Companion and dashboard coverage.

Coverage includes job dedupe/idempotency/supersession, stale lease ownership, bounded retries, failure isolation/dead-letter, security no-retry, central decisions, similarity-not-truth, current-evidence human approval, Gold/network isolation, lazy model import, adapter/cache, atomic swap/checksum/version/top-3 and resource concurrency/pressure. Existing asset/proposal/web tests also exercise the new lightweight integration hooks.

Seven Python deprecation warnings remain (existing FastAPI/websocket warnings plus FAISS SWIG wrappers). No coverage was disabled.

## Remaining bottlenecks / next recommended sprint

1. Free real RAM through normal operator usage; keep resource thresholds intact. Then explicitly process the existing local image through OpenCLIP and verify the persisted cache. No TikTok recovery is required.
2. Add independent local images and real assisted visual/web evidence. Strong corroboration or explicit REVIEW confirmation can create approved Entities; candidates/Gold cannot seed them.
3. Evaluate top-k on approved identities with adjudicated same-product/variant pairs; only then claim a reduction in REVIEW with preserved precision. False merges and AUTO accuracy remain unmeasured until suitable samples exist.
4. Retire legacy compatibility modules only after remaining consumers are migrated. No additional supplier/discovery/heavy topic work is needed now.

Stop reason: useful offline implementation and regression completed; **real inference blocked_by_resource_governor**, identity approval blocked_by_insufficient_evidence, and TikTok remains blocked_by_security_stop. Overall success remains partial rather than asserted complete.

References: [OpenCLIP official implementation](https://github.com/mlfoundations/open_clip), [FAISS official index IO](https://github.com/facebookresearch/faiss/wiki/Index-IO%2C-cloning-and-hyper-parameter-tuning).

## Measured local performance / index checkpoint

```json
{
  "light_jobs": {
    "jobs": 45,
    "avg_ms": 16.99999999254942,
    "min_ms": 15.000000013969839,
    "max_ms": 32.00000000651926
  },
  "index": {
    "generation": "abdb5c346a8c4615a426f1dcc3db6301",
    "embedding_version": "openclip-3.3.0-ViT-B-32-laion2b_s34b_b79k-fp32-v1:1bd3c7172de5b207ceac554f5ab5266166f3b9baccc9af5989bc801016d080ad",
    "observed_at": "2026-10-23T20:16:54.679371+00:00",
    "dimension": 512,
    "source_hash": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    "product_ids": [],
    "kinds": [],
    "sha256": "933c7bfa694dd494979d877684dbf1d58d5e3c9aed6e518c6c9a7b00ea43664d"
  },
  "historical_jobs": [
    {
      "job_type": "identity",
      "status": "queued",
      "reason_code": null,
      "count": 43
    },
    {
      "job_type": "identity",
      "status": "queued",
      "reason_code": "RESOURCE_BUSY",
      "count": 2
    },
    {
      "job_type": "identity",
      "status": "review",
      "reason_code": "REVIEW_CONFLICTING_VISUAL_RESULTS",
      "count": 1
    },
    {
      "job_type": "identity",
      "status": "superseded",
      "reason_code": "POLICY_SUPERSEDED",
      "count": 41
    },
    {
      "job_type": "identity",
      "status": "unresolved",
      "reason_code": "UNRESOLVED_GENERIC_TEXT",
      "count": 2
    },
    {
      "job_type": "identity",
      "status": "unresolved",
      "reason_code": "UNRESOLVED_NO_VISUAL",
      "count": 91
    },
    {
      "job_type": "index_rebuild",
      "status": "queued",
      "reason_code": null,
      "count": 1
    }
  ]
}
```
