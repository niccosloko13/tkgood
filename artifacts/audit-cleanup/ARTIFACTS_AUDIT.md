# Artifacts audit

Original artifacts total: 72.81 MiB (76,351,189 bytes). New audit outputs are separate; this total is the initial inventory.

| Category | Size | Retention |
|---|---:|---|
| historical text reports / generated outputs | 6.85 MiB (7,182,157 bytes) | REVIEW FIRST; not automatically expendable |
| checkpoint databases | 65.80 MiB (68,997,120 bytes) | REVIEW FIRST; not automatically expendable |
| screenshots / images | 0.16 MiB (163,523 bytes) | REVIEW FIRST; not automatically expendable |
| other | 0.01 MiB (8,389 bytes) | REVIEW FIRST; not automatically expendable |

## Important documentation and incident evidence

Keep docs/ as source documentation. Keep artifacts/selective-enrichment/, search-only-mode/, target-quarantine/, controlled-stage2/ and safe-collection-recovery/ incident/authorization evidence until explicit retention review. app/collection_mode.py reads the two selective-enrichment pilot reports to reconstruct historical context; scripts/controlled_stage2.py and resume_stage2.py also reconcile durable pilot reports. Some reports are operational no-replay markers, not disposable presentation output.

## Historical reports

Feature validation directories contain before/after JSON, HTML and Markdown. They are generated, but original timestamps/observations and past incident outcomes cannot generally be regenerated exactly. Reports can be regenerated only if their scripts, input DB/checkpoint, fixture versions, model and configuration survive. Label is REVIEW FIRST unless those inputs and purpose are confirmed.

## Reproducible outputs

Fixture-based benchmark/render reports are likely reproducible with pinned source, environment and fixtures. Live TikTok captures, manual reviews and historical security incidents are not reproducible test data. No production re-collection is authorized or necessary for this audit.

## Recovery potential

Checkpoint DBs are the majority of artifacts space (65.80 MiB). That is a conditional upper bound after retention approval, not SAFE DELETE. All artifacts together are 72.81 MiB; preserving code references and incident evidence reduces practical recovery. Exact per-directory sizes are in STORAGE_AUDIT.md/inventory.json. Hash duplicates cannot be added to other category savings without double counting.

The ZIP retains text reports after secret sanitization and excludes every checkpoint DB, screenshot/image, model and binary. Generated reports are not evidence that the associated feature code is removable.
