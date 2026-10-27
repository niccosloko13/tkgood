# Product Candidate Foundation

**Semântica atual:** status/confidence abaixo são legados, nunca confirmação de
mesmo produto físico. Usar `semantic_status` e as três dimensões descritas em
[PRODUCT_IDENTITY.md](PRODUCT_IDENTITY.md). Conteúdo histórico preservado abaixo.

Version: `product-candidate-v1`. Persisted Library only; no TikTok operations, external navigation, AI, resolver, promotion or physical-product clustering.

## Architecture

`app/product_detection.py` isolates phrase extraction, conservative Unicode normalization, source adapters, additive migration, confidence and corroboration. Configuration lives in `config/product_detection.json`. SQLite stores candidates, observed aliases, evidence, accumulated URLs and versioned runs with configuration snapshots. Existing collection tables are unchanged.

Only explicitly configured lexical patterns create hypotheses. Caption hashtags are extracted separately; search queries and profile URLs cannot originate a candidate or increase identity confidence. Profile bio can originate a low-confidence hypothesis. Short comment terms support an already observed, unambiguous phrase; they do not merge hypotheses. Raw evidence is retained. Arabic script is marked ar; other language labels remain null rather than guessed. No translation or stemming.

Confidence adds each identity source type weight once, plus configured independent-video and distinct-commenter bonuses. Single-source cap: 49%; observed cap: 69%; corroborated cap: 94%. These are heuristic support values, not calibrated probabilities. Repeated captures do not increase confidence. Corroboration requires two videos AND two observed creators, or caption + five distinct named commenters + bio. Caption and hashtag alone are not independent. Creator counts are observed identities, not proof of business independence.

Primary URL is the video underlying the strongest configured textual source. All prior source/URL records remain. Aliases are observed spellings or explicit short comment terms, not inferred synonyms. Exact normalized phrases share a textual hypothesis only, never a verified physical product. Manual confirmed/rejected storage is prepared; review actions are deferred.


Compact overview section, Library badges and existing drawer; PT-BR and ar-EG labels, logical layout/RTL, escaped raw text, safe navigable URLs. Top five recent hypotheses on overview, all associated hypotheses accessible from Library video badges.

## Real validation

Initial run: {"candidate_detection_rate": 0.35294117647058826, "candidates_corroborated": 0, "candidates_created": 7, "candidates_per_video": 0.4117647058823529, "candidates_updated": 0, "creators_per_candidate": 1.0, "evidence_count": 26, "evidence_created": 26, "evidence_per_candidate": 3.7142857142857144, "run_id": 1, "unique_creators": 4, "videos_per_candidate": 1.0, "videos_processed": 17, "videos_without_candidate": 11}

| Candidate | Confidence | Evidence rows | Videos | Creators | Status | Primary reference |
|---|---:|---:|---:|---:|---|---|
| Portable Dryer | 42% | 3 | 1 | 1 | observed | [video](https://www.tiktok.com/@elnazhamai/video/7685436719868464398) |
| 3 in 1 Window Cleaner | 42% | 3 | 1 | 1 | observed | [video](https://www.tiktok.com/@elnazhamai/video/7643873890845920526) |
| long-handled floor brush | 42% | 1 | 1 | 1 | observed | [video](https://www.tiktok.com/@tiomi9526/video/7671465879976086797) |
| Burger Patty Maker | 42% | 5 | 1 | 1 | observed | [video](https://www.tiktok.com/@elnazhamai/video/7670966128629288205) |
| dish brush | 42% | 6 | 1 | 1 | observed | [video](https://www.tiktok.com/@anya.bumag/video/7665799980480826642) |
| Soap dispenser | 42% | 6 | 1 | 1 | observed | [video](https://www.tiktok.com/@anya.bumag/video/7665799980480826642) |
| fruit spinner | 42% | 2 | 1 | 1 | observed | [video](https://www.tiktok.com/@sam.shan.shops/video/7649962108582399253) |

All seven hypotheses are observed; zero are corroborated. Six videos support them, eleven have no candidate. Four creators. Twenty-six evidence rows include historical captures and context; this does not mean twenty-six independent confirmations. Zero supporting identity comments were found for these phrases.

Observed aliases:
- Portable Dryer: Portable Dryer
- 3 in 1 Window Cleaner: 3 in 1 Window Cleaner
- long-handled floor brush: long-handled floor brush
- Burger Patty Maker: Burger Patty Maker
- dish brush: dish brush
- Soap dispenser: Soap dispenser
- fruit spinner: fruit spinner

Quality metrics (descriptive only): detection rate 6/17 = 35.29%; distinct candidates/video 7/17 = 0.4118; evidence/candidate 26/7 = 3.7143; videos/candidate 1; creators/candidate 1.

Rerun creates zero candidates/evidence; first_seen and existing URLs remain intact. Full machine-readable validation including every evidence row, alias and URL: `data/product_detection_validation.json` (local data, not committed).

## Limitations

Pattern vocabulary deliberately limits recall; unsupported phrases and languages are skipped. This foundation does not discover arbitrary unknown product names. Captions can mention multiple components: soap dispenser and dish brush remain separate hypotheses. Generic comments, account names, engagement metrics and unrelated commercial URLs cannot establish product identity. Existing links are preserved as external context without asserting a store/product relationship. No brand/model/price/category inference.

This workspace already contained substantial uncommitted work before the sprint. Changes for this sprint: app/product_detection.py; app/product_candidate_api.py; config/product_detection.json; additive integration in app/db.py and app/main.py; compact additions in app/static/index.html; scripts/detect_products.py and fixed background_runner task; tests/test_product_detection.py, tests/dashboard-ui.test.cjs, API mock in tests/dashboard.test.cjs; this document. No commit.

## Final checks

