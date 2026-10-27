# Intelligence Core — offline operational boundary

## Activation v1.2.2 — current policy

The existing gate now has independent text, visual-dependent and insufficient
paths. Specific caption + bound candidate can reach REVIEW without any image.
AUTO on text additionally needs recurring candidate observations and specific,
compatible comments from independent authors. Composition and explicit negation
remain REVIEW. Unresolved phrases can propose specific comment hypotheses but
cannot become confirmed candidates or entities through retrieval similarity.

Specificity combines existing product heads/signatures, compound structure,
specific modifiers, literal caption/comment support and recurrence. Generic heads
alone remain insufficient. Gold never enters this path.

The existing FAISS index now supports explicit PRODUCT_ENTITY,
CONFIRMED_OCCURRENCE and CANDIDATE_REFERENCE kinds. Candidate references have no
product_id and cannot authorize an entity, identity match or merge. Modalities
are separate from reference kinds. Retrieval history is additive. Atomic generation
validation/swap and old-generation fallback remain unchanged.

OpenCLIP is still lazy and local. The pinned checkpoint is loaded with the
[official PyTorch mmap/meta/assign recipe](https://docs.pytorch.org/tutorials/recipes/recipes/module_load_state_dict_tips.html)
to avoid duplicate resident weight copies. Strict assignment must succeed before
any inference. The constructor's initial random-weight warning is not an inference
result: all weights are subsequently assigned from the verified checkpoint.

The governor now reports RUN / WAIT / DEFER / STOP. RAM percentage is a pressure
signal; admission uses incremental available-memory budgets (1024 MiB cold mmap
load, 384 MiB warm inference), CPU <85%, critical STOP at <256 MiB or RAM >=98.5%.
Pressure waits/defer with a 20-second cooldown; it is never a permanent job failure
and does not exhaust the transient-error budget. One heavy worker, batch one, two
Torch CPU threads. The fixed background task is bounded to 180 seconds by default.
If still deferred at expiry, its checkpoint remains resumable on another explicit
activation; this is not an unlimited background service.

CUDA must be available in the actual Torch runtime, have enough free memory and
pass a small allocation/synchronization probe. Otherwise CPU is used. The installed
runtime is CPU-only. OOM defers work; GPU failure can fall back to CPU. No GPU or
Torch model is initialized at backend startup. Idle models unload after 30 seconds;
early timer wakes are rescheduled. The bounded worker also unloads on completion.

`POST /api/intelligence-core/matching-local` starts/reuses the existing fixed-task
launcher rather than blocking the backend. A worker-lifetime file lock enforces
single-worker operation. The worker denies all socket connections, uses local
assets, runs the targeted pilot, checks real embedding/cache/top-k, then processes
the 45 lightweight decisions. It never calls TikTok, Lens or a remote provider.

```powershell
.\.venv\Scripts\python.exe scripts/background_runner.py intelligence-worker
.\.venv\Scripts\python.exe scripts/report_core_activation.py
```

Purchase intent and consumer reactions are independent of identity. Their persisted
comment evidence is conservatively deduplicated by normalized text, including
anonymous copies. Rule classes distinguish buying/link/price/want/owned statements,
positive/negative reactions, questions and product/quality complaints. These are
lexical signals, not verified purchases or a final opportunity score. Missing product
quality stays insufficient_data. Trend/viral readiness still requires genuine history.

Production result: AUTO 0 / REVIEW 6 / UNRESOLVED 39; one real image embedding,
nine text embeddings, eight candidate-reference vectors. Original cold image
inference and the second cache hit are recorded in
`artifacts/core-activation/first-pilot.json`. See the activation report for evaluation
denominators, resource evidence and the unchanged security latch.

## Historical v1.1 foundation — policy superseded above

The production path is observation → existing candidate/visual provenance →
existing identity resolver → central gate → existing category → approved entity.
Gold is read only by `intelligence_evaluation.py`. Legacy Gold-assisted pilots
remain evaluation tools; production preparation does not consult pilot membership.
Supplier evidence stays separate. No module in this path issues browser commands.

Use `/intelligence-core` from the existing dashboard. It shows product, official
state, reason, source counts, category, separate quality dimensions and history
availability. Only REVIEW decisions enter the human identity review queue.
UNRESOLVED is not a request to manually confirm an unsupported hypothesis.
Adding local evidence is separate from confirming identity.

Existing upload, VisualProductEvidence, manual Lens registration, web evidence
and proposal reviews are retained. Their write endpoints refresh lightweight local
decisions transactionally. Manual provider/confidence/version fields are under
technical details in the legacy review. Preparing an image requires no name.
Lens remains assisted: Babi never uploads to or scrapes Lens.

## Explicit bounded execution

```powershell
.\.venv\Scripts\python.exe scripts/intelligence_core.py --evaluate
# Optional CPU stack, existing .venv only:
.\.venv\Scripts\python.exe -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements-intelligence.txt
# One-time official checkpoint download, pinned revision and SHA-256:
.\.venv\Scripts\python.exe scripts/install_intelligence_model.py
.\.venv\Scripts\python.exe scripts/intelligence_core.py --embeddings --rebuild-index --evaluate
```

The backend never downloads a model or loads torch/OpenCLIP on startup. Its
technical matching action is explicit, bounded and subject to the same governor.
CPU only, two inference threads, one cross-process heavy operation. Work waits if
CPU >=85%, RAM >=85%, or available RAM <2500 MiB. No process is killed to free RAM.
Checkpoint SHA, OpenCLIP version, model, weights and preprocessing revision form
the cache namespace. Text and original validated image bytes have separate SHA
keys. No TikTok CDN fallback exists.

## Decisions and entities

`config/intelligence_core.json` centralizes gate/matching, retry and resource
policy. The existing resolver's lexical configuration stays owned by that resolver.
The old visual hypothesis score is compatibility-only; it never authorizes AUTO.

AUTO requires a specific observed name, current-image visual proposal, literal
caption/comment support, two attested independent compatible listing sources, and
no observed contradiction/conflict. A single visual proposal cannot pass. Stale
or missing entity retrieval coverage defers an otherwise-supported decision to
REVIEW. Cosine similarities are heuristic signals, not calibrated probabilities.

Same-product matching uses the existing provenance-bound resolver, specific terms,
explicit brand/model-like features, independent web support, image/text cosine and
negative model/dimension/variant evidence. Weak similarity is insufficient rather
than another human review task. An accepted visual proposal alone is not entity
approval. Entities require AUTO or explicit confirmation of a current REVIEW.
No candidate or Gold label is modified; no entity or evidence is destructively merged.

## Jobs, history and index

Local identity, embedding and index jobs have deterministic input keys. Lightweight
and heavy work use separate lanes so model pressure cannot stall decisions.
Claims have exclusive lease tokens; stale owners cannot finish. Interrupted leases
and transient failures have at most three attempts and backoff. Resource pressure
pauses a heavy batch after its first refused item. Permanent failures go to
dead-letter, insufficient data terminates unresolved, SECURITY_BLOCK terminates
blocked with no retry. Explicit new evidence/policy creates a new work revision;
obsolete queued policies are superseded with retained history. There is no timer
daemon or browser retry loop. Work resumes on an explicit bounded local run.

The technical panel counts historical jobs by type/status; current decision counts
use each video's latest revision, including separate human outcome records. These
are different denominators. `blocked_jobs` preserves errors and recoverability.

Only approved entities enter FAISS. A selected image must match the approved
snapshot; otherwise an approved canonical-name text embedding is used. Metadata
records embedding modality. Empty indices are valid and do not need model loading.
Rebuilds with unchanged sources/version reuse the current generation. New builds
write and validate a temporary generation, flush index + mapping/checksum metadata,
then atomically replace one pointer. Old generations remain readable on failure.
Checksums are checked before FAISS deserialization. Index files are local trusted
artifacts; arbitrary uploaded index files are not supported.

## Quality and evaluation limits

Identity confidence, signal quality, viral potential, product quality, saturation
and commercial readiness remain separate. Missing data is null/insufficient_data,
never a zero quality score. Time series use actual first/local observation dates,
deduplicated observed comments and persisted detail counts; these are not publication
dates or a reconstructed history. Future topic/online/change-point adapters remain
declared insufficient_history; BERTopic/River/ruptures are not loaded.

Gold evaluation is read-only and downstream. Reported naming agreement explicitly
states literal matching and its denominator. It is not entity retrieval accuracy.
An entity-labelled retrieval corpus and adjudicated same-product pairs are still
needed for top-k retrieval accuracy and false-merge-rate evaluation. No AUTO decisions
means AUTO accuracy is null. Moving missing-evidence items out of REVIEW does not
prove better recall or less total human work.

References: [OpenCLIP](https://github.com/mlfoundations/open_clip),
[FAISS index IO](https://github.com/facebookresearch/faiss/wiki/Index-IO%2C-cloning-and-hyper-parameter-tuning).
