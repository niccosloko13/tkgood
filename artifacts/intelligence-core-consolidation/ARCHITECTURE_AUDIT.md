# Architecture audit — before source edits

| Component | Purpose | Keep | Refactor | Merge | Remove | Reason |
|---|---|---|---|---|---|---|
| bridge_commands / dev_control | Browser and ownership queues | yes |  |  | no | Security boundary; never merge with offline jobs |
| enrichment / night_discovery | Bounded capture checkpoints | yes |  |  | no | No browser execution this sprint |
| product_detection / candidates | Text proposals with provenance | yes |  |  | no | Candidates remain non-entities |
| visual_identification / visual_assets | Image storage, proposals, review history | yes |  |  | no | Reuse image hashes and current-image bindings |
| category VisualSearchProvider stub | Unused duplicate provider interface |  |  | yes | no | Deprecate compatibility stub; canonical interface in visual_identification |
| product_identity_resolver / candidate_semantics | Deterministic identity comparisons | yes |  |  | no | Core calls existing resolver; similarity adds evidence only |
| category_intelligence / planner | Classification and query metrics | yes |  |  | no | No taxonomy or classifier changes |
| gold_set | Human evaluation labels | yes |  |  | no | Only evaluation; excluded from production evidence loader |
| supplier_foundation | Listing evidence schema | yes |  |  | no | No supplier discovery |
| offline_intelligence | Inventory and diagnostic queues | yes |  |  | no | Diagnostic view; not identity input because it includes Gold diagnostics |
| events / browser_safety | Logs and persistent stop | yes |  |  | no | Preserve incident and security latch verbatim |
| browser.py / safe_actions | Legacy browser adapters |  | yes |  | no | No production callers; retain compatibility, no new use |
| visual hypothesis heuristic | Legacy proposal-level confidence |  | yes |  | no | Keep API compatibility; authoritative decisions move to central gate |
| local intelligence orchestration | No equivalent existing implementation |  | yes |  | no | Idempotent local jobs, decision records, approved entities |
| embedding / product retrieval | No equivalent existing implementation |  | yes |  | no | Lazy OpenCLIP/cache and atomic FAISS generation |
