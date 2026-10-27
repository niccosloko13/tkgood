# BABI — Offline Intelligence

Somente dados persistidos. ZERO navegação/requests TikTok, Computer Use, Lens, clear de latch, retry ou commit. Nenhum label humano ou classificação automática foi alterado.

## UNCLASSIFIED BREAKDOWN

| Grupo | Descrição | Vídeos |
|---|---|---|
| A | missing_data | 4 |
| B | generic_text | 8 |
| C | possible_visual_product | 12 |
| D | ambiguous_category | 0 |
| E | non_product_evidence | 0 |
| F | possible_classifier_coverage_gap | 12 |

Um grupo primário exclusivo por vídeo; tags sobrepostas e captions completas em audit.json. F é hipótese de lacuna lexical, não categoria nova. E exige evidência negativa explícita; ausência de candidate não significa não produto.

| ID | Grupo | Caption | Thumb | Comments | Creator | Unresolved | Candidate | Query | Detail | Compra (comments/contexto) |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 | C | sim | sim | não | sim | não | não | sim | sim | 0/False |
| 4 | C | sim | sim | não | sim | não | não | sim | sim | 0/True |
| 5 | A | não | sim | não | não | não | não | sim | não | 0/False |
| 6 | C | sim | sim | sim | sim | não | não | sim | sim | 2/False |
| 7 | A | não | não | não | não | não | não | sim | não | 0/False |
| 8 | A | não | não | não | não | não | não | sim | não | 0/False |
| 11 | A | não | sim | não | não | não | não | sim | não | 0/False |
| 12 | C | sim | sim | sim | sim | não | não | sim | sim | 0/False |
| 14 | C | sim | sim | não | sim | não | não | sim | não | 0/True |
| 17 | B | sim | sim | não | sim | não | não | sim | não | 0/False |
| 18 | F | sim | sim | sim | sim | não | não | sim | sim | 3/True |
| 19 | B | sim | sim | não | sim | não | não | sim | não | 0/True |
| 20 | B | sim | sim | não | sim | não | não | sim | não | 0/True |
| 21 | F | sim | sim | não | sim | não | não | sim | não | 0/False |
| 22 | B | sim | sim | não | sim | não | não | sim | não | 0/False |
| 23 | B | sim | sim | não | sim | não | não | sim | não | 0/False |
| 24 | B | sim | sim | não | sim | não | não | sim | não | 0/False |
| 25 | F | sim | sim | não | sim | não | não | sim | não | 0/False |
| 26 | B | sim | sim | não | sim | não | não | sim | não | 0/True |
| 27 | B | sim | sim | não | sim | não | não | sim | não | 0/True |
| 28 | F | sim | sim | não | sim | não | não | sim | não | 0/True |
| 29 | C | sim | sim | não | sim | não | não | sim | não | 0/False |
| 30 | C | sim | sim | não | sim | não | não | sim | não | 0/False |
| 31 | F | sim | sim | não | sim | não | não | sim | não | 0/True |
| 32 | F | sim | sim | não | sim | não | não | sim | não | 0/False |
| 33 | C | sim | sim | não | sim | não | não | sim | não | 0/False |
| 34 | C | sim | sim | não | sim | não | não | sim | não | 0/False |
| 35 | C | sim | sim | não | sim | não | não | sim | não | 0/False |
| 36 | F | sim | sim | não | sim | não | não | sim | não | 0/True |
| 37 | F | sim | sim | não | sim | não | não | sim | não | 0/False |
| 38 | C | sim | sim | não | sim | não | não | sim | não | 0/False |
| 39 | F | sim | sim | sim | sim | não | sim | sim | sim | 4/False |
| 41 | F | sim | sim | não | sim | não | não | sim | não | 0/False |
| 43 | C | sim | sim | não | sim | não | não | sim | não | 0/False |
| 44 | F | sim | sim | não | sim | não | não | sim | não | 0/False |
| 45 | F | sim | sim | não | sim | não | não | sim | não | 0/True |

Comments indica qualquer observação persistida; comments_count em audit.json é a amostra mais recente, persisted_comments_count inclui histórico (não autores únicos). Compra em caption é contexto comercial, não intenção de compra confirmada. Thumbnail indica referência armazenada, sem imagem acessada.

## CATEGORY AUDIT

| ID | Category | Subcategory | Product family | Confidence | Evidência | Alertas |
|---|---|---|---|---|---|---|
| 42 | electronics | — | — | 0.7 | caption: carregador | nenhum alerta heurístico |
| 40 | home | cleaning | cleaning tools | 0.7 | caption: limpeza | broad_context_term |
| 16 | home | laundry | laundry tools | 0.8 | candidate: portable dryer; caption: portable dryer | nenhum alerta heurístico |
| 15 | home | cleaning | cleaning tools | 0.8 | candidate: window cleaner; caption: window cleaner | nenhum alerta heurístico |
| 13 | home | cleaning | floor cleaning | 0.8 | candidate: floor brush; caption: floor brush; caption: floor cleaning | nenhum alerta heurístico |
| 10 | home | kitchen | food preparation | 0.8 | candidate: fruit spinner; caption: fruit spinner | nenhum alerta heurístico |
| 9 | home | kitchen | food preparation | 0.8 | candidate: burger patty; caption: burger patty | nenhum alerta heurístico |
| 3 | home | bathroom | dispensers | 0.8 | candidate: soap dispenser; caption: soap dispenser | bathroom_subcategory_context_not_proven |
| 1 | home | cleaning | cleaning tools | 0.5 | comment: vacuum cleaner; unresolved: vacuum cleaner | comment_or_unresolved_only, low_heuristic_confidence |

As nove classificações têm evidência/provenance auditada em audit.json. Confidence é peso heurístico máximo por regra, não probabilidade; captions repetidas e evidências derivadas não são fontes independentes. Vídeo 1 depende de comments/unresolved e tem confidence 0,5; 3 não prova contexto de Banheiro; 40 casa/limpeza é plausível mas o termo disparador é amplo. Não há base suficiente para alterar automaticamente taxonomy, family, classifier ou revisão humana.

## VISUAL QUEUE

| Prioridade | Quantidade |
|---|---|
| HIGH | 14 |
| MEDIUM | 12 |
| LOW | 11 |

| ID | Prioridade | Motivos |
|---|---|---|
| 2 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 4 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 5 | HIGH | has_thumbnail, likely_product, candidate_missing, no_text, comments_insufficient, category_unclassified |
| 6 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 11 | HIGH | has_thumbnail, likely_product, candidate_missing, no_text, comments_insufficient, category_unclassified |
| 12 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 14 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 29 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 30 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 33 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 34 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 35 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 38 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 43 | HIGH | has_thumbnail, likely_product, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 1 | MEDIUM | has_thumbnail, likely_product, has_unresolved, candidate_missing, generic_or_functional |
| 18 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 21 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 25 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 28 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 31 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 32 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 36 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 37 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 41 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 44 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 45 | MEDIUM | has_thumbnail, likely_product, candidate_missing, comments_insufficient, category_unclassified |
| 7 | LOW | likely_product, candidate_missing, no_text, comments_insufficient, category_unclassified, thumbnail_missing |
| 8 | LOW | likely_product, candidate_missing, no_text, comments_insufficient, category_unclassified, thumbnail_missing |
| 17 | LOW | has_thumbnail, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 19 | LOW | has_thumbnail, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 20 | LOW | has_thumbnail, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 22 | LOW | has_thumbnail, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 23 | LOW | has_thumbnail, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 24 | LOW | has_thumbnail, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 26 | LOW | has_thumbnail, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 27 | LOW | has_thumbnail, candidate_missing, generic_or_functional, comments_insufficient, category_unclassified |
| 42 | LOW | has_thumbnail, candidate_missing, generic_or_functional, comments_insufficient |

Fila de triagem, não lista de produtos confirmados. LOW inclui previews ausentes e casos com evidência fraca. Critérios, limitações e precedência documentados em docs/PRODUCT_IDENTIFICATION_PIPELINE.md. Nenhuma imagem foi baixada ou inspecionada e nenhum provider foi executado.

## GOLD SET GAP ANALYSIS

| ID FN | Causa primária | Causas diagnósticas | Motivo humano preservado |
|---|---|---|---|
| 1 | unknown_vocabulary | unknown_vocabulary, generic_caption | — |
| 4 | generic_caption | generic_caption, insufficient_text_evidence, missing_enrichment, likely_visual_dependency | — |
| 5 | no_text | no_text, insufficient_text_evidence, missing_enrichment, likely_visual_dependency | — |
| 6 | generic_caption | generic_caption, insufficient_text_evidence, missing_enrichment, likely_visual_dependency | — |
| 7 | no_text | no_text, insufficient_text_evidence, missing_enrichment | — |
| 8 | no_text | no_text, insufficient_text_evidence, missing_enrichment | — |
| 11 | no_text | no_text, insufficient_text_evidence, missing_enrichment, likely_visual_dependency | — |
| 12 | generic_caption | generic_caption, insufficient_text_evidence, missing_enrichment, likely_visual_dependency | — |
| 14 | generic_caption | generic_caption, insufficient_text_evidence, missing_enrichment, likely_visual_dependency | — |

15 reviews humanos, TP 5, FN 9. Recall strict name-aware: 35.71% (5/14 elegíveis). O unclear e os pendentes ficam fora. likely_visual_dependency é diagnóstico separado; não foi salvo como label/motivo humano. Não houve novo benchmark run.

## TEXT DETECTION GAPS

| Gap persistido mais recente por vídeo sem candidate | Vídeos |
|---|---|
| insufficient_evidence | 29 |
| generic_only | 2 |
| no_text | 4 |
| noise_filtered | 1 |
| unknown_product_phrase | 1 |

| Phrase | Status | Bloqueio | Modo |
|---|---|---|---|
| vacuum cleaner | pending | outside_approved_vocabulary | reviewable_suggestion |
| Mini Vacuum Cleaner | pending | outside_approved_vocabulary | reviewable_suggestion |

vacuum cleaner e Mini Vacuum Cleaner não casam com product_patterns do vocabulário aprovado. Foram retidas como noun-like unresolved, não rejeitadas por revisão humana. Decisões atuais: {&quot;statuses&quot;: {&quot;pending&quot;: 2}, &quot;vocabulary_reviews&quot;: 0, &quot;rejected_candidates&quot;: []}. Comments de um vídeo não provam identidade/corroboration. Suggestions são somente leitura; nada entrou automaticamente em candidates, vocabulário ou Gold Set. Precision após eventual aprovação permanece desconhecida.

## QUERY INTELLIGENCE

| Query | Aparições | Vídeos únicos | Duplicate rate observações | Creators | Candidates | Unresolved phrases | Classified | Ambiguous | Unclassified |
|---|---|---|---|---|---|---|---|---|---|
| home gadgets | 167 | 45 | 0.7305389221556886 | 29 | 8 | 2 | 9 | 0 | 36 |

BEST HISTORICAL QUERIES: home gadgets. LOW VALUE QUERIES: nenhuma pelo critério explícito duplicate ≥80% e zero vídeo com candidate. Somente uma query observada; não existe evidência comparativa de superioridade.

Taxas de observações incluem recapturas do mesmo viewport; não são novelty/duplicação entre sessões. As métricas do planner existentes estão separadas em audit.json/query_intelligence/session_metrics (home gadgets: 68 vistos por sessão somados, 28 novos, 40 conhecidos). Planner offline: home organization; componentes {&quot;base_priority&quot;: 10, &quot;novelty&quot;: 0, &quot;duplicate_penalty&quot;: 0, &quot;creators&quot;: 0, &quot;age&quot;: 2, &quot;underrepresented&quot;: 2.0}. Nenhuma execução real.

UNDEREXPLORED CATEGORIES (zero classificados, não ausência de produtos): beauty, pet, fitness, automotive, tools, baby, garden, fashion, wellness, travel, office, other.

## SUPPLIER FOUNDATION

SupplierListingEvidence definido em app/supplier_foundation.py, exportado em supplier-listing-evidence.schema.json. Sem tabela nova, scraping, request, associação real ou preço inventado. Listing é evidência de oferta; Product Identity Hypothesis é uma hipótese separada. IDs futuros são nullable. Preço/shipping exigem moeda; rating exige escala; timestamp exige timezone; match_confidence não confirma identidade. Arquitetura de texto + comentários + visual + web/supplier em docs/PRODUCT_IDENTIFICATION_PIPELINE.md.

## DASHBOARD / CATEGORY FILTER UX

Novo painel textual dentro de Overview/Vídeos: métricas locais, recall, principais gaps e filtros Casa, Cozinha, Limpeza, Organização, Unclassified, Revisão visual, Candidate ausente e Unresolved. Sem nova página ou redesign geral. O painel faz somente GET local e não contém imagens/links externos nem comandos de browser. Os controles de categoria/revisão preexistentes permanecem separados; nenhuma ação humana foi inferida.

## FILES CHANGED

- app/offline_intelligence.py
- app/offline_api.py
- app/supplier_foundation.py
- app/static/offline-intelligence.js
- app/main.py
- app/static/index.html
- tests/test_offline_intelligence.py
- tests/offline-insights.test.cjs
- scripts/offline_intelligence_report.py
- docs/PRODUCT_IDENTIFICATION_PIPELINE.md
- docs/NEXT_SESSION.md

Artefatos audit.json, visual-queue-v2.json, gold-fn-diagnostics.json, candidate-suggestions.json, supplier-listing-evidence.schema.json, before.json/checkpoint.db e verification.json. Workspace já continha mudanças anteriores; não houve revert/staging/commit.

## PRESERVATION

{&quot;changed_tables&quot;: [&quot;events&quot;, &quot;sqlite_sequence&quot;, &quot;system_state&quot;], &quot;changed_existing_sources&quot;: [&quot;app\\main.py&quot;, &quot;app\\static\\index.html&quot;], &quot;security_stop_unchanged&quot;: true, &quot;integrity_check&quot;: &quot;ok&quot;, &quot;foreign_key_check&quot;: [], &quot;browser_runtime_unchanged&quot;: true, &quot;browser_security_history_unchanged&quot;: true, &quot;browser_security_clearance_unchanged&quot;: true}

Somente tabelas operacionais podem variar com heartbeat/restart. Gold Set, benchmark, classifier history, taxonomy, detector, evidence, resolver, queries e enrichment são comparados com o checkpoint anterior. Security stop da home preservado. Nenhuma alteração em extensão ou controles de browser.

## TEST RESULTS

| Suite | Passed | Task SUCCEEDED |
|---|---|---|
| python | 277 | 59b4cc4b04344cd28a70c0cc00aa7e97 |
| node_dashboard | 114 | 9e5013d523f141fca01e9988c2ed4ce9 |

Python: quatro warnings de depreciação preexistentes. Node: zero falhas/skips. API e asset locais: 200 OK. Category provenance inválida: zero. Testes usam bancos temporários e fixtures, sem TikTok real. Cobrem grupos, prioridades, Gold diagnostics, sugestões sem aprovação, métricas/denominadores, contratos supplier e UX local sem requests externos. Nenhum teste existente foi removido. Logs em .runtime/logs/task-ID.json e .log.

## NEXT ACTION WHEN HUMAN RETURNS

Revisar primeiro os 14 HIGH e os alertas de categoria 1/3/40 usando apenas evidência persistida. Conferir as duas suggestions sem aprovação automática. Ampliar reviews humanos offline antes de adaptar vocabulário/classifier. Imagens não persistidas e qualquer coleta/validação TikTok ficam blocked_by_security_stop; não retomar automaticamente. Supplier search/Lens permanecem fora desta execução.
