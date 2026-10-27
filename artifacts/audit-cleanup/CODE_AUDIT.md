# Static code and dependency audit

Evidence is static, conservative and not proof of removability. Runtime plugin registration, CLI entry points, templates and external API clients are not fully resolved. No modules imported, no servers started, no requests submitted.

## Scripts with no known static caller

- `scripts/local_visual_assets_report.py`: no filename/stem reference in app/extension/scripts/tests/docs/config/root text. CLI entry point=True. REVIEW FIRST, not confirmed dead.
- `scripts/offline_intelligence_report.py`: no filename/stem reference in app/extension/scripts/tests/docs/config/root text. CLI entry point=True. REVIEW FIRST, not confirmed dead.
- `scripts/report_intelligence_core.py`: no filename/stem reference in app/extension/scripts/tests/docs/config/root text. CLI entry point=True. REVIEW FIRST, not confirmed dead.
- `scripts/validate_connection_panel.py`: no filename/stem reference in app/extension/scripts/tests/docs/config/root text. CLI entry point=True. REVIEW FIRST, not confirmed dead.

## Modules with no known static reference


## Endpoint consumer gaps (router prefixes resolved)

Constant APIRouter prefixes included. Dynamic-prefix matches do not prove each verb/parameter variant is used.

- `app/selective_api.py:52` GET `/api/search-only-intelligence`: no literal consumer found; REVIEW FIRST.

## Exact normalized Python function bodies

Function names/decorators/docstrings ignored; >=20 AST nodes. Shared helpers and test stubs are expected.

- `app/comments.py:49` (folded); `app/comments.py:101` (fold)
- `app/gold_set.py:19` (digest); `app/intelligence_core.py:18` (fingerprint)
- `app/visual_identification.py:261` (aware); `app/visual_identification_api.py:59` (timezone_required); `app/visual_identification_api.py:93` (timestamp)
- `app/visual_identification.py:267` (bounded_aliases); `app/visual_identification_api.py:99` (alias_bounds)
- `scripts/discovery_session.py:9` (call); `scripts/read_creator_profiles.py:8` (call)
- `scripts/local_visual_assets_report.py:44` (esc); `scripts/offline_intelligence_report.py:44` (text)
- `scripts/local_visual_assets_report.py:45` (table); `scripts/visual_identification_report.py:53` (table)
- `tests/test_core_activation.py:156` (guard); `tests/test_intelligence_core.py:251` (authorize)
- `tests/test_manual_captcha_recovery.py:22` (checked); `tests/test_stage2_resume.py:24` (fresh)

## Dependencies

- torch: **USED**. Evidence: app/intelligence_embeddings.py:168, app/intelligence_embeddings.py:212, app/intelligence_embeddings.py:137. Optional intelligence/model pipeline; not necessary for search-only mode
- torchvision: **USED** transitively. Evidence: open_clip/transform.py:9 and open_clip/utils.py:8. Required by optional OpenCLIP pipeline.
- open_clip_torch: **USED**. Evidence: app/intelligence_embeddings.py:169. Optional intelligence/model pipeline; not necessary for search-only mode
- faiss-cpu: **USED**. Evidence: app/intelligence_index.py:20, app/intelligence_index.py:63. Optional intelligence/model pipeline; not necessary for search-only mode
- numpy: **USED**. Evidence: app/intelligence_index.py:19, app/intelligence_index.py:64, app/trend_history.py:264. Optional intelligence/model pipeline; not necessary for search-only mode
- psutil: **USED**. Evidence: app/intelligence_embeddings.py:30, app/intelligence_jobs.py:109, tests/test_core_activation.py:100. Static imports only; transitive/dynamic use can exist
- fastapi: **USED**. Evidence: app/browser_safety.py:56, app/category_api.py:2, app/collection_mode.py:4, app/db.py:174, app/db.py:268, app/db.py:278, app/db.py:283, app/db.py:286. Static imports only; transitive/dynamic use can exist
- uvicorn: **USED**. Evidence: run.py:30, tests/test_bridge.py:12, tests/test_capture.py:13, tests/test_dev_control.py:14. Static imports only; transitive/dynamic use can exist
- pydantic: **USED**. Evidence: app/category_api.py:3, app/comment_schemas.py:2, app/creator_schemas.py:5, app/dev_control.py:10, app/discovery_api.py:3, app/enrichment_api.py:2, app/gold_set_api.py:3, app/intelligence_api.py:4. Static imports only; transitive/dynamic use can exist
- Pillow: **USED**. Evidence: app/intelligence_embeddings.py:213, app/visual_assets.py:11, tests/test_local_visual_assets.py:9. Static imports only; transitive/dynamic use can exist
- pytest: **DEV ONLY**. Evidence: tests/test_authenticated_dom.py:2, tests/test_backlog.py:2, tests/test_bridge.py:11, tests/test_candidate_corroboration.py:4, tests/test_capture.py:12, tests/test_category_intelligence.py:3, tests/test_command_api_contract.py:5, tests/test_comments.py:8. Static imports only; transitive/dynamic use can exist
- psutil: **USED**. Evidence: app/intelligence_embeddings.py:30, app/intelligence_jobs.py:109, tests/test_core_activation.py:100. Static imports only; transitive/dynamic use can exist
- linkedom: **DEV ONLY**. Evidence: package-lock.json:9, package.json:5, tests/category-ui.test.cjs:2, tests/connection-panel.test.cjs:2, tests/dashboard-ui.test.cjs:5, tests/dashboard.test.cjs:5, tests/dom-fixture.cjs:1, tests/gold-set-ui.test.cjs:5. 

No dependency is confirmed removable solely from a missing direct import. torchvision is imported by open_clip transitively; optional ML is not equivalent to unused code. Keep requirements and lockfiles.

psutil is declared in both requirements files with the same version. This is declaration duplication, not two installations and not removal authorization.
