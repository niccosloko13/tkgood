# Discovery + Category Intelligence — relatório

## BEFORE

- Library: 45 vídeos; candidates: 8; evidências: 65.
- Creators enriquecidos (entidades): 29; usernames distintos da Library: 29.
- Sem classificações/taxonomia de categoria persistidas antes desta missão. Checkpoint: data/category_mission_before.json.

## AFTER

- Library: 45; novos vídeos: 0; duplicados desta missão: 0; usernames distintos: 29.
- Classified: 9; ambiguous: 0; unclassified: 36.
- Candidates: 8; unresolved: 2; evidências: 65.
- Gold Set: 15 reviews; TP 5, FP 0, FN 9, TN 0. Labels e benchmark não alterados.

## QUERY PERFORMANCE

Métricas abaixo são do histórico existente, não de novas buscas desta missão. Denominador de novelty/duplicate = soma de vídeos únicos por sessão; repetições de viewport são separadas. Candidate/creator/classified rate = vídeos distintos atribuídos à query. Ausência de execução = taxas null, não zero de qualidade.

| Query | Runs | Vistos | Novos | Duplicados conhecidos | Novelty | Duplicate | Creators | Candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| home gadgets | 7 | 68 | 28 | 40 | 41.2% | 58.8% | 29 | 8 |
| home finds | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| amazon home finds | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| useful home products | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| viral home products | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| kitchen gadgets | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| kitchen finds | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| cleaning gadgets | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| cleaning tools | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| home organization | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| organization gadgets | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| bathroom gadgets | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| laundry gadgets | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| smart home gadgets | 0 | 0 | 0 | 0 | — | — | 0 | 0 |
| tiktok made me buy it home | 0 | 0 | 0 | 0 | — | — | 0 | 0 |

Melhor novelty observada: home gadgets.
Maior duplicate rate observada: home gadgets. Não há base suficiente para comparação entre queries não executadas.

Planner atual: home organization; componentes: `{"base_priority": 10, "novelty": 0, "duplicate_penalty": 0, "creators": 0, "age": 2, "underrepresented": 2.0}`.

## CATEGORY DISTRIBUTION

- unclassified: 36.
- electronics: 1.
- home: 8.

Subcategorias: {"unclassified": 37, "cleaning": 4, "laundry": 1, "kitchen": 2, "bathroom": 1}.

## RUNTIME

- Execuções do novo runner: 1. Sessões TikTok desta missão: 0. Nenhum comando TikTok criado.
- Stop reason: security_stop. HTTP 403 persistido antes da missão impediu toda navegação; sessão não foi reaberta nem refreshed.
- Security latch: {"reason": "HTTP 403: https://www.tiktok.com/@vitrineglei/video/7673992589036506388", "observed_at": "2026-10-22T12:25:59.604Z"}.
- Runner local validado: parada imediata antes de submit; limites, checkpoint e retomada de sessão já capturada exercitados em SQLite de teste.
- Validação end-to-end de SEARCH/discovery ao vivo NÃO realizada devido ao stop. Não foi contornado.
- Chrome persistente/aba não tocados. Não houve engagement, coleta externa ou enriquecimento real. Backend reiniciado somente pelo devctl silencioso; logs em .runtime/logs.

## ARCHITECTURE

- Taxonomia configurável PT-BR/ar-EG; categorias independentes de identidade física. Classificador determinístico com provenance, ambiguidade e unclassified.
- Histórico automático aditivo e revisões humanas separadas. Nenhuma Gold label vira regra de categoria. Sem alteração de detector/weights/vocabulary existentes.
- HOME_DISCOVERY_V1, métricas derivadas, planner explicável, runner opt-in limitado/retomável e prioridade de enrichment transparente.
- Biblioteca com filtros e contagens; Overview compacto; correção humana e registro visual manual. Provider visual é só interface; Lens não automatizado.

## PRESERVATION

- Todos os hashes de tabelas preexistentes de negócio iguais antes/depois. Somente events/system_state/sqlite_sequence variaram por backend/devctl/heartbeat.
- Bridge commands e security latch idênticos. Configs anteriores e testes legados intactos. Novas tabelas são aditivas.
- Sem merge, Product entity final, IA, Supplier Discovery ou Opportunity Score. Sem commit/staging.

## FILES CHANGED

- `config/category_taxonomy.json`
- `config/discovery_intelligence.json`
- `app/category_intelligence.py`
- `app/category_api.py`
- `app/night_discovery.py`
- `app/db.py`
- `app/main.py`
- `app/enrichment.py`
- `app/static/index.html`
- `app/static/category-intelligence.js`
- `tests/test_category_intelligence.py`
- `tests/category-ui.test.cjs`
- `docs/CATEGORY_INTELLIGENCE.md`
- `docs/NEXT_SESSION.md`
- `artifacts/night-discovery/REPORT.md`

## TEST RESULTS

- 235 Python passed, 4 warnings de depreciação já existentes. Task 01128dd77c6549d6b30ba248815af881 SUCCEEDED.
- 103 Node/dashboard passed. Task 02dc3c673df24b5881381435bdd0e410 SUCCEEDED.
- Nova lógica: taxonomia/classifier/ambiguous/unknown, fontes fracas, idempotência aditiva, filtros/correção humana, query rates/cooldown, runner limits/security/checkpoint/resume.
- Regressões de dedup existentes permanecem cobertas pela suíte completa.
- QA visual isolado file://, PT-BR/ar-EG em1440 e390px, sem overflow nem erros JS, filtro Casa=8. Sem conexão ao perfil Chrome/TikTok. `.runtime/category-visual/validation.json`.
- git diff --check passou; diff --stat e status revisados incluindo trabalho sujo anterior, sem revert/commit.

## LIMITATIONS / NEXT RECOMMENDED SPRINT

- Revisão humana das categorias e dos 36 unclassified com dados persistidos; ampliar regras somente com evidência/revisão, sem alterar Gold Set automaticamente.
- Regras pequenas em inglês/português: não é NLP/tradução universal. Outros idiomas podem ficar unclassified. Confidence heurística não garante classificação correta.
- Nenhuma correção humana de categoria ou evidência visual foi inventada no banco real; formulários aguardam o usuário.
- Sessão/403 precisa de revisão humana normal antes de qualquer validação de discovery ao vivo. Não limpar latch automaticamente nem solicitar bypass.
- Futuros providers visuais ainda não executam buscas. Registros manuais são propostas não confirmadas.
- Recomenda-se validar um lote controlado após resolução legítima do bloqueio, antes de executar várias sessões.
