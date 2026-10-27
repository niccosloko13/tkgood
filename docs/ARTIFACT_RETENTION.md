# Artifact retention

Keep `artifacts/current/` for active run/checkpoint reports and current operator
documentation. Move no files as part of this policy rollout.

Put completed sprint reports under `artifacts/archive/` only after checking their
references and preserving original timestamps. Do not remove checkpoints until
rollback need, production callers and incident-history retention have been
reviewed. The pilot reports under `artifacts/selective-enrichment/` are read by
`app/collection_mode.py` to recover both navigation challenge contexts. Stage
reports also serve as no-replay intent records. Treat database checkpoints,
search provenance, trend sources, Gold Set reviews, security history, quarantines
and browser profile as durable user data.

Current audit found 14 checkpoint SQLite files (about 65.8 MiB). Their contents
were preserved. Compression/removal requires a separate retention review. No
automatic housekeeping is configured.
