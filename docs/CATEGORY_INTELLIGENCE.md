# Discovery + Category Intelligence v1

Taxonomy: `config/category_taxonomy.json` (`category-taxonomy-v1`). Small taxonomy,
14 top-level categories, 9 home subcategories. IDs stay language neutral; PT-BR
and ar-EG labels are separate. Category never confirms physical product identity.

Classifier uses existing captions, simple hashtags, latest sampled comments,
provenance-bound candidate phrases, unresolved phrases, creator bio and search
appearances. Human Gold Set labels are never classifier inputs. Every matched
term retains source entity, source ID, text and URL. Strongest matching source
determines each rule score: repeated comments/observations do not multiply score.
Creator/query context cannot reach the configured minimum alone. Competing close
categories/subcategories become ambiguous; competing families remain null.
Unknown input remains unclassified. Scores are heuristics, not probabilities.

`video_category_classifications` stores immutable classifier history with input
fingerprint, versions and evidence. Identical rerun inserts nothing. Human
category corrections append to `human_category_reviews`, link the prior automatic
classification and override the effective display only. Automatic history stays.
This is separate from Gold Set review/benchmark and candidate identity semantics.

Query pack/planner/runner/enrichment settings: `config/discovery_intelligence.json`.
HOME_DISCOVERY_V1 contains 15 selected queries. Query history reuses existing
`discovery_sessions`, `discovery_session_videos` and `search_observations`.
Novelty uses sum(new_videos)/sum(unique_videos per session); duplicate rate uses
the complementary known-video count, not repeated viewport sightings. Raw
duplicate appearances are exported separately. Candidate/classification/creator
rates use distinct library videos attributed to that query, not impression count.
Zero denominator gives null. These metrics describe coverage, not correctness.
Planner combines configurable base priority, age, observed novelty/duplication,
creator diversity, underrepresented subcategories and a repetition cooldown.
Unrun queries have null performance, not invented novelty. Queries are never deleted.

Night runner is explicit opt-in from Library or local POST endpoint, not a startup
job/scheduler. Default limits: 12 sessions, 25 videos/session, 200 total new videos,
3600s runtime, 15s cooldown, 2s polling, limited command/readiness waits. Existing
extension enforces 5 scrolls/90s maximum independently. Uses existing SEARCH and
DISCOVER_MORE_RESULTS through the existing command API implementation, preserving
readiness, pacing, Chrome/tab reuse and dedup. No direct TikTok client or browser
launcher. Persistent run/checkpoint records retain stage and command/session IDs.
Captured sessions can resume offline processing; active commands are observed,
not blindly resubmitted. Runtime expiry with a live command leaves a waiting run.
Backend restart marks the worker interrupted without altering its command.
Explicit resume is available in UI/API. Limits remain relative to original run.
Stop request is honored after current operation, never mid-observation.

Security latch, missing connection/login, failed command, missing session or
unconfirmed readiness stops the runner. No latch clearing, bypass, retry loop,
identity change, generic click, engagement or new Chrome/tab creation.
While HTTP403 latch is active, runtime validation stops before issuing any command.
Processing newly discovered persisted videos reuses the existing detector in its
own transaction. No threshold, weights or vocabulary changes. Detector reruns
retain its existing idempotency guarantees. Classification runs before/after
detector so newly persisted phrases can supply category context. Per-query metrics
are retained at completed checkpoints and available as current derived metrics.

Enrichment remains a separate, max-five-video batch action. Discovery ranking
is transparent and configurable (category, absent candidate, weak caption,
unresolved, comments, thumbnail, buying terms). Existing new-video preference is
preserved first, followed by this score and prior priorities. No mass enrichment.

Visual foundation: `visual_product_evidence`, `VisualSearchProvider` interface,
manual assisted evidence form. Nothing calls Lens or another provider. A recorded
possible name/reference is not a new candidate, label or confirmed match.

UI stays inside existing Library with a compact Overview summary. Filters include
category/subcategory/family/candidate status/candidate presence/unresolved/creator/
source query/enrichment; counts are explicit. Review forms persist through the
dashboard's ordinary polling. No new page or general redesign. Remote thumbnail
behavior of the existing library is unchanged; Gold Set click-to-load is untouched.

## Local API

- GET `/api/category-intelligence`: current summary, taxonomy, inventory, queries, plan, runs.
- GET `/api/category-intelligence/library?category=home&subcategory=cleaning`: filtered metadata.
- POST `/api/category-intelligence/classify`: classify persisted library only.
- POST `/api/category-intelligence/videos/{internal_id}/review`: explicit human correction.
- GET `/api/category-intelligence/videos/{internal_id}/history`: automatic/manual/visual history.
- POST `/api/category-intelligence/videos/{internal_id}/visual-evidence`: manual registration only.
- POST `/api/category-intelligence/night/start`: explicitly start bounded runner.
- POST `/api/category-intelligence/night/start?resume_id=ID`: resume saved run.
- POST `/api/category-intelligence/night/{id}/stop`: request clean stop.

No browser validation should be attempted while the security latch remains active.
No Supplier Discovery, Opportunity Score, advanced Product entity, AI or clustering.
