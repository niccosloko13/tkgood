# BABI ? audit and cleanup report

TOTAL PROJECT SIZE: 4806.32 MiB (5,039,787,939 bytes) (~5.04 GB decimal), 31,621 files.

AUDIT ZIP SIZE: approximately 2.55 MiB compressed; exact final bytes, SHA256 and CRC result in PACKAGE_VALIDATION.json beside the ZIP. ZIP is a sanitized review copy, not a runnable environment/session backup.

FILES: project inventory 31,621; packaged files listed in FILES.txt (ZIP root). See PACKAGE_VALIDATION.json for final package count. Required TREE.txt, FILES.txt, DB_SCHEMA.txt, GIT_STATUS.txt, GIT_DIFF_STAT.txt and DEPENDENCIES.txt are included at ZIP root. No .env.example/pyproject.toml existed to include.

SAFE DELETE: 7,211 files / 94.57 MiB (99,162,740 bytes). Bytecode/test caches only, after confirming relevant processes are stopped. No files deleted.

PROBABLY SAFE: 672 files / 117.19 MiB (122,884,140 bytes). Two isolated dashboard UI test profiles; confirm no Chrome instance owns them.

REVIEW FIRST: 960 files / 140.42 MiB (147,240,369 bytes). Runtime, historical checkpoints/reports and generated data require retention and ownership checks.

CORE: 111 files / 1.95 MiB (2,047,514 bytes). Additional KEEP items (tests/scripts/docs, data, Git, signing key, dependencies, Chrome identity) are not disposable. FILE_CLASSIFICATION.json classifies every original file; DUPLICATES.json adds proven exact-hash relations. No module was conclusively LEGACY solely from age/no caller.

## TOP SPACE WASTERS

Largest consumers are not all waste:

1. .venv: 3317.37 MiB (3,478,514,034 bytes); torch alone includes a 2,325,803,578-byte dnnl.lib. Do not hand-delete files from an installed package; optional environment reduction would be a separate dependency/installation change.
2. browser-profiles: 638.65 MiB (669,674,938 bytes); active account/profile and cache. DO NOT DELETE as a directory. Cache-only cleanup would require separate browser-aware approval; no cookies/profile files were opened.
3. data/models: 577.18 MiB (605,219,813 bytes); OpenCLIP checkpoint is referenced, even though not needed for search-only mode.
4. .runtime: 168.56 MiB (176,749,129 bytes); includes two 58.60-MiB UI test profiles and live ownership/config/diagnostic state. Do not clear wholesale.
5. artifacts: 72.81 MiB (76,351,189 bytes); primarily historical checkpoint DBs and text reports. Not automatically redundant.

## POSSIBLE DEAD CODE

Four CLI/report/debug scripts have no external static stem references: local_visual_assets_report.py, offline_intelligence_report.py, report_intelligence_core.py, validate_connection_panel.py. These may still be intentional manual entry points. No confirmed dead app module was found by this conservative scan. One API has no literal consumer after resolving constant router prefixes: GET /api/search-only-intelligence (a read-only review endpoint). Duplicate function bodies, scripts and exact locations are in CODE_AUDIT.md and STATIC_REFERENCES.json. Runtime helpers under .runtime include refactor_runtime.py/export_analysis_bundle.py/report_detail_metrics.py and UI check scripts; these are ad-hoc operational artifacts excluded from the ZIP, not proof of safe deletion.

## DUPLICATE RESPONSIBILITIES

Challenge text patterns repeat in safety.js and session_signals.js. Global/browser latches intentionally replicate policy across process boundaries. browser_safety, safe_collection and manual_captcha_recovery have separate explicit clearance contracts. Stage 1/2 scripts repeat orchestration/reporting while sharing safe_collection. Search-only and legacy candidate/backlog priorities overlap in scheduling purpose but use different evidence. Trend observations/snapshots/source links are distinct provenance layers. ARCHITECTURE_REVIEW.md gives file/line evidence and consolidation risks. No security/session or query module is approved for removal.

## UNUSED DEPENDENCIES

None confirmed removable. All declared runtime dependencies have direct or confirmed transitive uses. torchvision is imported by installed open_clip/transform.py:9 and utils.py:8. pytest and Node linkedom are DEV ONLY. psutil==7.2.2 is declared in both requirements files (duplicate declaration, not duplicate installation). Torch/OpenCLIP/FAISS are optional feature dependencies, not proven unused. requirements-intelligence.txt can remain separate without running those features.

## DATABASE / RUNTIME

21 project SQLite files exported as DDL/counts only, excluding browser/profile DBs. Main data/product_hunter.db is 8,572,928 bytes. There were no project DB WAL/SHM sidecars in the inventory. All SQLite reads used immutable read-only mode; no migrations, updates or vacuum. Main DB has 53 videos, 203 search observations, 22 detail observations, 428 trend snapshots and 428 source links. Historical queues/events/observations need retention design, not deletion. Schemas include constraints/indexes/triggers/views where present; implicit auto-indexes are represented by table constraints. DATABASE_INVENTORY.json lists every exported DB/table count. Tables with no rows are not automatically dead.

## POTENTIAL SPACE RECOVERY

Conservative cache-only: 94.57 MiB (99,162,740 bytes).

Cache + isolated test profiles, once ownership is checked: 211.76 MiB (222,046,880 bytes).

Conditional REVIEW FIRST pool: 140.42 MiB (147,240,369 bytes), additional and disjoint from the first two groups; not an approved recovery estimate. Exact-hash savings are theoretical and overlap these groups. No installed dependencies, model or active browser profile counted as safe recovery. Logical bytes may differ from NTFS allocated/free-space changes.

## RECOMMENDED CLEANUP ORDER

1. Review SAFE TO DELETE cache paths with relevant processes stopped; explicitly authorize any cleanup later.
2. Confirm the two isolated UI test profiles are inactive; preserve useful diagnostics before a separate deletion approval.
3. Review checkpoint/report retention and no-replay/incident dependencies; then consider optional environment/model footprint in a separate, tested dependency plan. Preserve DBs, account profile, signing key and global security state.

## Package controls and limits

Excluded .venv, node_modules, .git, .runtime, browser profiles, all data/ content, DB files, keys, cookies, .env, media/screenshots, ML models, embeddings/indexes and binary backups. Source/config/tests/docs/scripts and text artifacts are included. Known local dev credential and sensitive JSON/header/query values are redacted in ZIP copies; originals are untouched. PACKAGE_POLICY.json inside ZIP lists sanitized copies/exclusions. Secret scanning is heuristic plus exact known credential matching, not a formal guarantee for arbitrary unknown secrets. Root Git files contain status/stat only, no patches/remotes.

Static reachability cannot prove dead code. Hashing was bounded to 512 MiB and files <=64 MiB outside environments/node_modules/Git/private profiles; 136 exact duplicate groups were found. Full size scan covered all readable original files (0 errors). New audit output/ZIP overhead is excluded from the initial project total. No server/browser was started, no collection/retry ran, no file was deleted/moved, no import/dependency/data was changed, no commit was made.
