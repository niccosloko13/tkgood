# BABI V1 EXECUTION PLAN

## PARTE 2 — DISCOVERY LOOP, TREND ENGINE V2, TOP OPPORTUNITIES E BACKTEST

### 1. MISSÃO DA FASE

A Parte 2 transforma a Babi de um coletor confiável em uma ferramenta de decisão.

Objetivo principal:

Identificar quais produtos estão começando a ganhar força, explicar por que estão subindo e medir depois se a previsão estava correta.

Esta fase deve trabalhar primeiro com os dados já existentes.

A coleta ao vivo NÃO é pré-requisito para começar.

Enquanto o latch global permanecer ativo, toda a implementação e validação inicial devem ocorrer offline sobre os dados persistidos.

---

## 2. PRINCÍPIOS OBRIGATÓRIOS

A Parte 2 deve obedecer:

- não reconstruir a arquitetura;
- usar o DiscoveryRunner criado na Parte 1;
- preservar SQLite, histórico, provenance, Gold Set e snapshots;
- não reativar Direct Video Enrichment;
- não abrir vídeos individualmente;
- não criar Stage 3, Stage 4 ou novos recovery flows;
- não instalar frameworks pesados;
- não criar um score opaco único;
- não inventar métricas ausentes;
- toda conclusão deve possuir evidência explicável;
- toda métrica temporal deve ser derivada de observações reais e timestamps reais;
- nenhuma ação no TikTok deve ocorrer enquanto o safety contract impedir.

---

## 3. ARQUITETURA ALVO

Fluxo canônico:

DISCOVERY RUNNER
       ↓
SEARCH OBSERVATIONS
       ↓
TREND SNAPSHOTS
       ↓
TREND ENGINE V2
       ↓
LIFECYCLE ENGINE
       ↓
CANDIDATE RANKING
       ↓
TOP OPPORTUNITIES
       ↓
WHY / EVIDENCE
       ↓
BACKTEST

O Safety Gate continua separado:

BROWSER / COMPANION
       ↓
SAFETY GATE
       ↓
DISCOVERY RUNNER

Safety responde somente se a coleta pode prosseguir.

Safety não calcula tendência, ranking ou oportunidade.

---

## 4. USAR PRIMEIRO OS DADOS EXISTENTES

Antes de qualquer nova coleta:

auditar os dados atuais e gerar um snapshot de baseline.

No mínimo levantar:

- número de vídeos;
- número de candidatos;
- número de search observations;
- número de trend snapshots;
- número de creators únicos;
- número de queries únicas;
- distribuição de observações por candidato;
- distribuição temporal das observações;
- candidatos com 1 observação;
- candidatos com 2 observações;
- candidatos com 3+ observações;
- séries com métricas numéricas suficientes;
- séries sem dados suficientes.

Criar:

artifacts/phase2-intelligence/BASELINE.md

Nenhuma classificação nova deve ser aplicada antes de registrar esse baseline.

---

## 5. TREND ENGINE V2

Criar um engine determinístico e explicável.

Não usar ML inicialmente.

Cada candidato/produto deverá ter, quando possível:

first_seen
last_seen
age_hours

observation_count

query_count
query_spread

creator_count
creator_spread

recurrence

views_velocity
likes_velocity
comments_velocity
shares_velocity
favorites_velocity

acceleration

duplicate_density

freshness

saturation_signal

evidence_quality

Cada campo precisa indicar:

- valor;
- unidade;
- janela temporal;
- quantidade de observações usadas;
- confidence/evidence quality;
- motivo para indisponibilidade quando não puder ser calculado.

---

## 6. RECURRENCE

Definir recurrence como presença repetida ao longo do tempo.

Não contar duplicatas do mesmo capture como nova recorrência.

Considerar:

- observações em momentos diferentes;
- queries diferentes;
- creators diferentes;
- intervalos temporais reais.

Exemplo conceitual:

produto aparece 1 vez
→ baixa recorrência

produto aparece novamente 6h depois
→ recorrência crescente

produto aparece em múltiplas queries e creators
→ recorrência forte

Recurrence nunca deve ser inferida apenas por duplicação técnica.

---

## 7. QUERY SPREAD

Medir em quantas queries semanticamente distintas o candidato aparece.

Exemplo:

home gadgets
home finds
cleaning gadgets

Se o mesmo produto aparece nas três:

query_spread = 3

Preservar também:

- primeira query;
- queries posteriores;
- timestamps;
- rank em cada query.

Query spread é sinal de propagação.

Não é prova de vendas.

---

## 8. CREATOR SPREAD

Medir quantos creators distintos estão associados ao mesmo candidato.

Separar:

same_creator_recurrence
different_creator_spread

Um único creator repetindo o mesmo produto não deve ter o mesmo peso que vários creators independentes.

Creator spread precisa considerar deduplicação por identidade conhecida.

---

## 9. VELOCITY

Calcular velocity somente quando houver pelo menos dois pontos numéricos válidos para a mesma métrica.

Exemplo:

views_velocity =
(view_count_t2 - view_count_t1) / elapsed_hours

O mesmo conceito para:

- likes;
- comments;
- shares;
- favorites.

Regras:

- timestamps precisam ser válidos;
- valores precisam ser numéricos;
- delta negativo inesperado deve ser marcado para revisão de qualidade;
- ausência de views não pode ser substituída por outra métrica;
- não extrapolar além da janela observada.

---

## 10. ACCELERATION

Acceleration mede mudança da velocity.

Só calcular quando houver histórico suficiente.

Conceito:

velocity_1
velocity_2
↓
acceleration = velocity_2 - velocity_1

Classificações possíveis:

RISING
STABLE
FALLING
INSUFFICIENT

Não produzir acceleration com apenas dois snapshots totais quando isso não gerar duas janelas de velocity válidas.

---

## 11. AGE

Calcular:

age_hours = now/reference_time - first_seen

Quando create_time original estiver disponível e confiável, manter separado:

content_age
babi_detection_age

Nunca misturar:

- idade real do conteúdo;
- tempo desde que a Babi descobriu o conteúdo.

---

## 12. DUPLICATE DENSITY

Medir a proporção de resultados repetidos em relação às observações.

Exemplo conceitual:

muitas observações
poucos vídeos/creators novos
→ duplicate density alta

Duplicate density elevada pode indicar:

- saturação;
- query estreita;
- baixa novidade;
- conjunto pequeno de conteúdos dominantes.

Não declarar saturação apenas com essa métrica.

---

## 13. SATURATION SIGNAL

Criar uma dimensão independente.

Usar sinais como:

- duplicate density;
- repetição dos mesmos creators;
- repetição dos mesmos vídeos;
- grande volume histórico sem crescimento de diversidade;
- queda de novidade;
- estabilidade/queda de acceleration;
- ampla presença com baixa expansão recente.

Estados:

LOW
MEDIUM
HIGH
INSUFFICIENT

Saturação não deve ser derivada de uma única variável.

---

## 14. EVIDENCE QUALITY

Cada candidato deve possuir qualidade de evidência.

Exemplo:

HIGH
MEDIUM
LOW
INSUFFICIENT

Considerar:

- quantidade de observações;
- cobertura temporal;
- quantidade de métricas válidas;
- diversidade de queries;
- diversidade de creators;
- consistência dos dados.

Um candidato não pode virar BREAKOUT com evidência insuficiente apenas porque uma métrica parece alta.

---

## 15. LIFECYCLE ENGINE

Consolidar um único lifecycle canônico.

Estados:

DISCOVERED
EARLY_SIGNAL
EMERGING
ACCELERATING
BREAKOUT
MAINSTREAM
SATURATED
DECLINING

Cada transição precisa ser explicável.

Não usar thresholds arbitrários sem registrar a justificativa.

Primeira versão pode utilizar regras conservadoras.

DISCOVERED:
- poucas observações;
- evidência insuficiente;
- sem expansão confirmada.

EARLY_SIGNAL:
- recorrência inicial;
- sinal em mais de um momento ou query;
- pouca evidência ainda.

EMERGING:
- recurrence crescente;
- query spread ou creator spread aumentando;
- alguma velocity positiva;
- saturation baixa.

ACCELERATING:
- velocity crescente;
- acceleration positiva;
- diversidade aumentando;
- evidência suficiente.

BREAKOUT:
- forte expansão temporal;
- crescimento consistente;
- múltiplas queries/creators;
- acceleration alta;
- evidência forte.

MAINSTREAM:
- grande distribuição;
- elevada presença;
- crescimento ainda positivo, porém maturidade maior.

SATURATED:
- duplicate density elevada;
- pouca novidade;
- expansão desacelerando;
- muita presença já consolidada.

DECLINING:
- velocity e/ou acceleration negativas de forma sustentada;
- redução de recorrência ou expansão;
- evidência temporal suficiente.

---

## 16. SEM SCORE ÚNICO OPACO

Não implementar nesta fase:

BABI SCORE = 91

A Babi deve mostrar dimensões independentes.

Exemplo:

Momentum: HIGH
Velocity: RISING
Acceleration: RISING
Recurrence: HIGH
Query Spread: 4
Creator Spread: 5
Saturation: LOW
Evidence Quality: MEDIUM
Lifecycle: EMERGING

Se futuramente houver Opportunity Score, ele deverá ser derivado e explicável.

---

## 17. MOMENTUM

Momentum pode existir como resumo qualitativo.

Estados:

LOW
MEDIUM
HIGH
VERY_HIGH
INSUFFICIENT

Momentum deve refletir combinação documentada de:

- recurrence;
- velocity;
- acceleration;
- query spread;
- creator spread;
- freshness.

Não usar Product Quality, supplier readiness ou comments intent como requisito para momentum.

---

## 18. TOP OPPORTUNITIES

Criar read model específico:

TopOpportunity

Campos mínimos:

candidate_id
display_name
lifecycle
momentum
first_seen
last_seen
age_hours
observation_count
query_spread
creator_spread
velocity_summary
acceleration_summary
saturation
evidence_quality
why[]
risks[]
insufficient_signals[]
last_updated

Não exigir enrichment direto.

---

## 19. WHY — EXPLICAÇÃO OBRIGATÓRIA

Toda oportunidade precisa responder:

Por que a Babi está mostrando isso?

Gerar reasons determinísticos baseados em evidência.

Exemplos:

Apareceu em 4 queries diferentes.
Foi observado por 5 creators distintos.
A recorrência aumentou nas últimas 12 horas.
A velocidade de comentários cresceu.
Novos creators apareceram desde a última janela.
A saturação ainda está baixa.

Também mostrar sinais negativos:

Poucas observações.
Views indisponíveis.
Creator spread ainda baixo.
Histórico temporal curto.

Nunca gerar WHY via texto inventado sem referência aos dados persistidos.

---

## 20. RANKING

Top Opportunities deve priorizar sinais positivos sem esconder incerteza.

Primeira versão considerar:

- lifecycle;
- momentum;
- freshness;
- acceleration;
- recurrence;
- query spread;
- creator spread;
- saturation;
- evidence quality.

Não incluir nesta fase:

- supplier price;
- margin;
- direct comments intent;
- visual identity certainty como requisito universal;
- product quality não observada.

Candidates com evidência insuficiente podem aparecer em seção separada:

WATCHLIST

---

## 21. WATCHLIST

Criar Watchlist para sinais interessantes ainda não comprovados.

Exemplo:

EARLY WATCH

Produto X

Motivo:
apareceu em 2 queries nas últimas 3h

Limitação:
apenas 2 observações

Isso evita promover cedo demais para Top Opportunities.

---

## 22. BACKTEST

O backtest é obrigatório.

Objetivo:

medir se as classificações da Babi possuem valor preditivo.

Quando um candidato receber uma avaliação:

HIGH momentum
EMERGING
ACCELERATING

persistir um prediction checkpoint.

Campos mínimos:

candidate_id
prediction_time
lifecycle
momentum
evidence_snapshot
metrics_snapshot
why_snapshot

Depois avaliar:

+6h
+24h
+72h

quando houver dados suficientes.

Resultados:

GREW
STABLE
DECLINED
UNKNOWN

---

## 23. BACKTEST METRICS

Medir pelo menos:

HIGH candidates that grew
HIGH candidates that failed
MEDIUM candidates that grew
LOW candidates that unexpectedly grew
precision-like rate
coverage
insufficient-data rate

Não chamar isso de precisão estatística formal se os critérios não suportarem essa interpretação.

Mostrar claramente tamanho da amostra.

---

## 24. NÃO USAR GOLD SET COMO INPUT

Gold Set permanece somente para avaliação.

É proibido alimentar:

- ranking;
- lifecycle;
- momentum;
- WHY;
- opportunity;

com labels do Gold Set.

Gold Set pode ser usado para verificar qualidade depois.

---

## 25. DISCOVERY LOOP V1

Depois de validar o Trend Engine offline, integrar ao DiscoveryRunner.

Fluxo:

QUERY PACK
    ↓
DISCOVERY RUNNER
    ↓
OBSERVATIONS
    ↓
TREND SNAPSHOTS
    ↓
TREND ENGINE
    ↓
TOP OPPORTUNITIES

O Discovery Loop não é um crawler infinito.

Cada execução deve ser limitada e possuir:

run_id
started_at
finished_at
queries_planned
queries_completed
results_seen
new_videos
duplicates
observations_created
snapshots_created
stop_reason
security_state

---

## 26. QUERY PACK

Usar inicialmente queries existentes e validadas.

Não criar centenas de queries.

Persistir por query:

query
results
new_videos
duplicates
unique_creators
candidate_matches
observed_at

Posteriormente o planner poderá aprender quais queries produzem melhores sinais.

Não implementar aprendizado do planner agora.

---

## 27. RECORRÊNCIA DO DISCOVERY LOOP

Não criar scheduler complexo nesta fase.

O runner deve permitir execuções manuais/repetidas.

Exemplo conceitual:

run now
run later
compare observations

A arquitetura deve permitir automação futura sem depender dela.

---

## 28. SAFETY DURANTE DISCOVERY LOOP

O contrato da Parte 1 continua valendo.

Antes da coleta:

PAGE = HEALTHY
SESSION = CONFIRMED
GLOBAL SECURITY = OK

Durante:

parar imediatamente em:

403 global
challenge
captcha
verify human
logged out
host inesperado

Direct Video Enrichment continua:

PAUSED

Search-only permanece o único modo ativo.

---

## 29. ESTADO ATUAL DE LATCH

No início desta fase existe um latch global persistente de challenge.

Não liberar automaticamente.

Enquanto estiver ativo:

- implementar offline;
- testar offline;
- gerar Top Opportunities a partir do histórico;
- executar backtest histórico quando possível.

Somente o fluxo de recuperação existente pode autorizar nova coleta.

Não criar um novo recovery flow.

---

## 30. DASHBOARD — NOVA PRIORIDADE

A tela principal não deve ser dominada por:

Connection
Companion
Security
Heartbeat

Esses itens devem permanecer disponíveis em:

Sistema / Diagnóstico

A home deve priorizar:

TOP OPPORTUNITIES
EARLY WATCH
TREND CHANGES
RECENT DISCOVERIES

---

## 31. CARD DE TOP OPPORTUNITY

Exemplo:

Portable Window Cleaner

Lifecycle: EMERGING
Momentum: HIGH

First seen: 8h
Observations: 14
Queries: 4
Creators: 5

Velocity: RISING
Acceleration: RISING
Saturation: LOW
Evidence: MEDIUM

WHY
✓ apareceu em novas queries
✓ novos creators surgiram
✓ recorrência aumentou
✓ velocidade está crescendo
✓ saturação ainda baixa

RISKS
! histórico curto
! views incompletas

---

## 32. HISTÓRICO TEMPORAL

Ao abrir uma oportunidade:

mostrar timeline.

Exemplo:

14:00 — first seen — home gadgets
16:00 — repeated — home finds
18:00 — new creator
20:00 — query spread increased
22:00 — velocity increased

Cada evento deve apontar para provenance existente.

---

## 33. TREND CHANGE EVENTS

Quando uma dimensão mudar significativamente:

persistir evento.

Exemplos:

LIFECYCLE_CHANGED
MOMENTUM_CHANGED
ACCELERATION_CHANGED
SATURATION_CHANGED
QUERY_SPREAD_INCREASED
CREATOR_SPREAD_INCREASED

Evitar gerar eventos idênticos repetidos em cada cálculo.

---

## 34. IDEMPOTÊNCIA

Recalcular Trend Engine não pode:

- duplicar snapshots;
- duplicar predictions;
- duplicar change events;
- alterar dados brutos;
- apagar provenance.

Mesmo input deve gerar mesmo resultado determinístico.

---

## 35. PERFORMANCE

Trend Engine deve funcionar localmente sem carregar Torch/OpenCLIP.

Não importar dependências pesadas no caminho principal.

Objetivo:

Babi Core

funcionar independentemente do stack visual.

---

## 36. TESTES OBRIGATÓRIOS — TREND

Criar testes para:

- single observation;
- two observations;
- three or more observations;
- invalid timestamp;
- missing metrics;
- duplicate capture;
- same creator recurrence;
- distinct creator spread;
- query spread;
- velocity;
- acceleration;
- negative deltas;
- saturation;
- insufficient evidence;
- deterministic recomputation.

---

## 37. TESTES OBRIGATÓRIOS — LIFECYCLE

Fixtures para:

DISCOVERED
EARLY_SIGNAL
EMERGING
ACCELERATING
BREAKOUT
MAINSTREAM
SATURATED
DECLINING

Cada fixture deve explicar quais evidências causam a classificação.

Evitar thresholds mágicos não documentados.

---

## 38. TESTES OBRIGATÓRIOS — TOP OPPORTUNITIES

Testar:

- ordering;
- ties;
- insufficient evidence;
- high saturation penalty;
- fresh emerging candidate;
- stale candidate;
- missing views;
- candidate without creator information;
- deterministic WHY;
- risks generation.

---

## 39. TESTES OBRIGATÓRIOS — BACKTEST

Testar:

- prediction snapshot is immutable;
- 6h evaluation;
- 24h evaluation;
- 72h evaluation;
- insufficient future data;
- no future leakage;
- Gold Set isolation;
- repeated backtest does not duplicate results.

---

## 40. NO FUTURE LEAKAGE

Backtest nunca pode usar dados posteriores ao prediction time para criar a previsão original.

Separar rigorosamente:

information available at T0

de:

future observations

Esse requisito é crítico.

---

## 41. REPORT DE EXPLICAÇÃO

Criar:

artifacts/phase2-intelligence/REPORT.md

Incluir:

- baseline;
- arquitetura implementada;
- fórmulas;
- thresholds;
- lifecycle rules;
- quantidade por lifecycle;
- Top Opportunities;
- Watchlist;
- exemplos de WHY;
- backtest disponível;
- limitations;
- dados insuficientes;
- testes;
- pendências.

Não esconder resultados ruins.

---

## 42. OUTPUT DO CODEX

Ao finalizar, responder com:

BASELINE:
...

TREND ENGINE:
implemented / partial

LIFECYCLE:
...

TOP OPPORTUNITIES:
...

WATCHLIST:
...

BACKTEST:
...

DATA USED:
...

NEW DATA COLLECTED:
0 unless explicitly authorized

PYTHON TESTS:
...

JAVASCRIPT TESTS:
...

REGRESSIONS:
...

GLOBAL SECURITY:
...

DIRECT VIDEO ENRICHMENT:
PAUSED

NEXT RECOMMENDED ACTION:
...

---

## 43. SCOPE FREEZE

Durante a Parte 2 NÃO implementar:

- Direct Video Enrichment;
- comments collection;
- creator profile collection;
- automatic Google Lens;
- supplier discovery;
- price scraping;
- BERTopic;
- Temporal;
- Crawlee runtime;
- ruptures em produção;
- ML-based ranking;
- opaque Opportunity Score;
- proxy systems;
- fingerprint manipulation;
- security bypass;
- new recovery architecture.

---

## 44. DEFINIÇÃO DE PRONTO — PARTE 2

A fase só é considerada concluída quando:

✓ baseline dos dados atuais criado

✓ Trend Engine v2 determinístico

✓ recurrence funcionando

✓ query spread funcionando

✓ creator spread funcionando

✓ velocity funcionando quando há dados

✓ acceleration funcionando quando há dados

✓ age separado corretamente

✓ saturation signal implementado

✓ evidence quality implementado

✓ lifecycle canônico funcionando

✓ Top Opportunities funcionando

✓ WHY explicável

✓ Watchlist funcionando

✓ predictions persistidas

✓ backtest sem future leakage

✓ dashboard prioriza oportunidades

✓ Safety continua separado

✓ Direct Enrichment continua PAUSED

✓ nenhum dado histórico perdido

✓ regressão Python verde

✓ regressão JavaScript verde

---

## 45. RESULTADO DE PRODUTO ESPERADO

Ao final desta fase, a pergunta:

O que está começando a viralizar?

deve produzir uma resposta semelhante a:

TOP OPPORTUNITIES

1. Produto A
   Lifecycle: EMERGING
   Momentum: HIGH
   Saturation: LOW

   WHY:
   - apareceu em 4 queries;
   - passou de 2 para 5 creators;
   - recurrence aumentou;
   - velocity está subindo;
   - ainda existe baixa repetição saturada.

2. Produto B
   Lifecycle: EARLY_SIGNAL
   Momentum: MEDIUM
   Saturation: LOW

   WHY:
   - descoberta recente;
   - apareceu novamente em outra query;
   - creator spread começou a aumentar.

WATCHLIST

Produto C
- sinal interessante;
- somente 2 observações;
- histórico ainda insuficiente.

A Babi v1 não precisa saber tudo sobre o produto.

Ela precisa ser capaz de:

DETECTAR CEDO
ACOMPANHAR NO TEMPO
PRIORIZAR CORRETAMENTE
EXPLICAR A DECISÃO
VALIDAR DEPOIS SE A PREVISÃO FUNCIONOU

Sem commit.