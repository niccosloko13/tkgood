# DiscoveryRunner v1

`app.discovery_runner.DiscoveryRunner` is the canonical persistence, queue,
bounded-run and report lifecycle for search collection. Stage is a budget profile
from `config/discovery_contract.json`: Stage 1 allows one previously observed
query and ten visible results; Stage 2 allows up to five authorized Casa queries,
30 new videos and 180 seconds. Both stay search-only with zero scrolls.

The existing `safe_collection` functions are deprecated compatibility adapters.
The authenticated API and command-result/claim paths call DiscoveryRunner.
`scripts/quarantine_stage1.py`, `controlled_stage2.py` and `resume_stage2.py`
remain deprecated operator adapters so old commands/checkpoints keep working.
Each report embeds the canonical `discovery_run` shape and retains its historical
fields until Part 2 verifies external consumers and migrates/removes adapters.

DiscoveryRunner reads the canonical read-only Safety decision before queueing or
claiming search work. It does not clear security stops, collect outside the
explicit existing Stage authorizations, or schedule Stage 3/direct enrichment.
