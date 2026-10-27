# Babi v1 — Fase 2: Intelligence offline

## Resultado

Fase executada integralmente sobre o SQLite existente. Nenhuma coleta, navegação TikTok, abertura de vídeo, alteração de browser profile ou liberação de security latch foi feita. **Novos dados coletados: 0.**

O baseline anterior à classificação está em [BASELINE.md](BASELINE.md).

## Baseline utilizado

| Dado persistido | Quantidade |
| --- | ---: |
| Vídeos | 53 |
| Candidatos | 8 |
| Search observations | 203 |
| Trend snapshots | 428 |
| Creators ligados a vídeos | 31 |
| Queries únicas | 5 |

Janela de observação: `2026-10-21T16:23:12Z` a `2026-10-25T18:18:48Z`.

## Arquitetura implementada

```text
DiscoveryRunner (após capture persistido)
  -> search observations / trend snapshots existentes
  -> Trend Engine v2 offline
  -> top_opportunities + change events + prediction checkpoints
  -> API /api/opportunities
  -> dashboard: Top Opportunities e Early Watch
```

O Safety Contract permanece fora desse caminho. O motor não lê browser, não cria comandos e não pode liberar o latch. `DiscoveryRunner` apenas recalcula a projeção local depois que uma captura já foi persistida.

Arquivos principais: `app/trend_engine_v2.py`, `config/trend_engine_v2.json`, `docs/TREND_ENGINE_V2.md`, `app/static/opportunities.js`.

## Fórmulas e regras

- **Recurrence**: quantidade de `capture_id` distintos; duplicatas dentro da mesma captura não contam novamente.
- **Query/creator spread**: queries normalizadas e creators observados distintos.
- **Duplicate density**: `1 - unique_video_count / observation_count`.
- **Velocity**: `(métrica_t2 - métrica_t1) / horas decorridas`, somente com dois snapshots numéricos válidos.
- **Acceleration**: diferença entre as duas últimas velocities, somente com três pontos válidos.
- **Age**: `babi_detection_age_hours` é separado de `content_age_hours`; este último permanece indisponível sem create time real.
- **Saturation**: exige repetição suficiente e mais de um sinal local; não deriva só de duplicate density.
- **Evidence quality**: combina quantidade de observações/capturas, spread de queries e, para HIGH, spread de creators e janela temporal.

Os thresholds explícitos estão em `config/trend_engine_v2.json`; não existe score único ou opaco.

## Lifecycle

Regras conservadoras e explicáveis:

- `DISCOVERED`: evidência insuficiente.
- `EARLY_SIGNAL`: recorrência inicial, ainda com cobertura limitada.
- `EMERGING`: evidência média/alta, spread em query ou creator e sem saturação alta.
- `ACCELERATING`, `BREAKOUT`, `MAINSTREAM`: exigem condições progressivamente mais fortes de evidence, spread e velocity/acceleration.
- `SATURATED`: repetição local alta, baixa novidade/independência.
- `DECLINING`: velocity e acceleration observadas em queda.

Distribuição atual: `EMERGING=5`, `EARLY_SIGNAL=2`, `SATURATED=1`. Não houve `ACCELERATING`, `BREAKOUT`, `MAINSTREAM` ou `DECLINING` com a evidência disponível.

## Top Opportunities

| Candidato | Lifecycle | Momentum | Evidence | Saturation |
| --- | --- | --- | --- | --- |
| Soap dispenser | EMERGING | HIGH | HIGH | LOW |
| dish brush | EMERGING | HIGH | HIGH | LOW |
| Burger Patty Maker | EMERGING | MEDIUM | MEDIUM | MEDIUM |
| fruit spinner | EMERGING | MEDIUM | MEDIUM | INSUFFICIENT |
| long-handled floor brush | EMERGING | MEDIUM | MEDIUM | MEDIUM |

Exemplo de WHY para **Soap dispenser**: apareceu em 5 queries distintas, foi observado por 2 creators distintos, ocorreu em 16 capturas distintas, possui ao menos uma velocity positiva observada e o sinal local de saturação está baixo. Essas razões contêm IDs de evidência no read model.

## Watchlist

| Candidato | Lifecycle | Momentum | Limitação principal |
| --- | --- | --- | --- |
| escova | EARLY_SIGNAL | MEDIUM | evidence quality LOW |
| 3 in 1 Window Cleaner | EARLY_SIGNAL | LOW | creator spread baixo; cobertura limitada |
| Portable Dryer | SATURATED | LOW | saturação HIGH e creator spread baixo |

## Prediction checkpoints e backtest

Foram persistidos 2 checkpoints imutáveis para os candidatos elegíveis de momentum HIGH. Há 6 avaliações (2 checkpoints × 6h/24h/72h), todas `UNKNOWN`: a janela futura exigida não está coberta por novas observações locais. Isso é o comportamento conservador esperado.

Uma avaliação `UNKNOWN` não é terminal: quando uma janela futura passar a existir, ela é atualizada para o resultado observado sem duplicar a linha. O checkpoint que originou a previsão permanece imutável.

O backtest separa rigidamente o estado em `prediction_time` da evidência posterior. Candidate membership também só é ativada depois de `product_candidate_evidence.observed_at`. Gold Set não é consultado por ranking, lifecycle, WHY ou backtest.

| Métrica atual 24h | Valor |
| --- | ---: |
| Amostra | 2 |
| HIGH que cresceram | 0 |
| HIGH que falharam | 0 |
| Taxa semelhante a precisão | indisponível |
| Dados insuficientes | 100% |

Não é uma estimativa estatística formal; a amostra é pequena e a cobertura futura ainda não existe.

## Idempotência e dados

Uma segunda execução com o mesmo input retornou `changed=0`, `events=0`, `prediction_checks=0`. O processo não duplicou snapshots, change events ou predictions e não alterou dados brutos.

Ao final: `top_opportunities=8`, `trend_change_events=0`, `prediction_checkpoints=2`, `prediction_evaluations=6`. As contagens originais de `videos=53`, `product_candidates=8`, `search_observations=203` e `trend_snapshots=428` foram preservadas.

## Dashboard

A home agora começa por **TOP OPPORTUNITIES** e **EARLY WATCH**, com lifecycle, momentum, spreads, velocity, acceleration, saturation, evidence quality, WHY, riscos e limitações. Connection/Safety permanecem nas telas operacionais. O painel é somente leitura e faz uma única consulta local a `/api/opportunities`.

## Testes

- Python completo: **554 passed, 7 warnings**, exit code 0.
- JavaScript completo: **174 passed, 0 failed**, exit code 0.
- Testes novos cobrem observação única, recurrence, query/creator spread, velocity, acceleration, delta negativo, saturation, lifecycle, WHY determinístico, idempotência, checkpoint imutável, no future leakage e ordering/Watchlist.

Os avisos Python existentes são de APIs deprecated de FastAPI/websockets e bindings SWIG.

## Limitações e pendências

- A maior limitação é diversidade temporal/creator: os dados disponíveis ainda são curtos e concentrados. Nenhuma conclusão afirma vendas, demanda total ou tendência de plataforma.
- O primeiro backtest útil depende de futuras observações reais após checkpoints; não há valor para preencher artificialmente.
- Change events começarão a ser registrados somente quando um read model anterior mudar com novos dados.
- O safety latch global continua ativo. Search-only só poderá operar depois da recuperação humana já existente confirmar `HEALTHY / CONFIRMED / OK`.
- Direct Video Enrichment continua `PAUSED`.
