# Visual identity completion V1

The existing core uses local assets and the existing VisualSearchProvider contract.
Normal operation is `/intelligence-core` -> **Identificar imagens disponíveis**.
No product-name/provider/SHA/manual-confidence input is needed. The call starts
the fixed `visual-identity-worker` through the existing background runner; it
shares the existing heavy-worker lock and processes at most 14 actual local assets.

```powershell
.\.venv\Scripts\python.exe scripts/background_runner.py visual-identity-worker
.\.venv\Scripts\python.exe scripts/report_visual_identity.py
```

The remote adapter reuses `OPENAI_API_KEY` and `OPENAI_BASE_URL`. Supported HTTPS
API hosts are explicitly validated; the configured service here is OpenRouter,
using `openai/gpt-4.1-mini`. The key is never logged or stored in evidence. Image
requests use validated local bytes as data URIs, with no persisted text or Gold in
the first prompt. Missing credentials, invalid responses and challenges are
explicit failure states, not successful visual identifications. No API retry loop
or redirect forwarding is implemented.

Flow: prepare local context -> image-only alternate visual provider -> 1–3
observed hypotheses -> explicit-alias normalization -> cached image/name embeddings
and existing typed FAISS top-3 -> local text/category cross-check -> a bounded
domain-filtered public web search -> cited evidence -> existing Decision Gate.
The gate code/thresholds are unchanged. Text-only decisions remain valid.

Automatic Lens is unavailable. Lens is AVAILABLE_ASSISTED with
LENS_ASSISTED_REQUIRED. The operator can download the local image and submit that
image to Lens manually; there is no name-first Lens query or pretend Lens result.
The automatic alternate is vision-model image analysis, not reverse-image search.

Provider analysis and cited search stages are checkpointed in existing visual
pilot records. Image/model cache reuse does not create a new independent vote.
The active provider response is selected separately from archived responses,
preserving provider hypothesis order and human-accepted evidence. All records
remain in history. Suggested VPE rows do not confirm a Product Entity.

Text cross-check reports SUPPORTED, NEUTRAL or CONFLICT. Coarse category support
does not force identity. Web search accepts only cited HTTPS URLs from configured
manufacturer domains, at most three results. Product-type compatibility and
publisher-domain grouping are not human visual verification, SKU equality or
verified supply-chain independence. Such flags remain unverified unless actually
reviewed; web titles cannot silently replace visual names with brand/SKU guesses.

Quality observations retain reasons and observed/partial/insufficient states for
visibility, problem/solution clarity, before/after, transformation, novelty and
repeatability. No Viral/Opportunity Score is calculated. Purchase Intent and other
independent dimensions continue if visual identity is unresolved or deferred.

NEEDS_VISUAL priority uses REVIEW gaps first, explicit user-provided historical
IDs only when assets exist, then unresolved generic text and other cases. Gold
labels do not enter production queue inference/provider inputs. Gold is used only
by the downstream evaluation export. Source/public context is collected before
vision but used only afterward for cross-checking.

Upload is fallback only. A usable image hides Adicionar imagem; replacement is a
technical action. The existing `persist_visual_asset(video_id, bytes,
source_metadata)` is the future acquisition contract. A future legitimate capture
may pass bytes already visible/allowed by its runtime, once per hash, while the
current security-stop checks remain authoritative. No capture, TikTok navigation
or CDN retrieval is implemented here.

See `artifacts/visual-identity-completion/REPORT.md` for the actual one-image pilot,
source citations, strict naming metrics and remaining uncertainty. One ambiguous
frame does not establish global accuracy or exceptional human-review frequency.
