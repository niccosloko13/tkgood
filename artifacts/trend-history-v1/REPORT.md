# BABI — Trend History + Velocity Engine v1

Sprint offline: dados históricos reais, sem coleta, navegação TikTok, CDN, provider
externo ou engagement. Nenhum commit. Identity e as oito dimensões existentes foram
preservados; o histórico temporal é uma camada aditiva.

## Snapshots imported

**392 snapshots**, a partir de 200 registros originais de vídeo e suas coortes:

| Target | Targets | Snapshots |
|---|---:|---:|
| VIDEO | 45 | 200 |
| CANDIDATE | 8 | 55 |
| PRODUCT_ENTITY | 0 | 0 |
| CATEGORY | 2 | 32 |
| SUBCATEGORY | 4 | 50 |
| PRODUCT_FAMILY | 5 | 55 |
| Total | 64 | 392 |

Os 200 snapshots de vídeo correspondem a 167 observações de search, 21 de detalhe
e 12 amostras de comentários persistidas. Os outros 192 são agregações locais,
não novas coletas nem observações independentes adicionais. Coortes se sobrepõem.

Snapshots guardam timestamp UTC, tipo/ID do target, video_id/referência quando
aplicável, source, hash do payload, métricas nullable e coverage. A tabela de
proveniência mantém source keys estáveis. Segunda importação: **zero inserções**.

Somente números persistidos são normalizados. O parser existente transforma,
por exemplo, `31.2K` em 31.200; `Curtida`/`Favoritos` continuam NULL. Valores
arredondados mantêm a limitação de precisão da captura. As fontes brutas originais
continuam intactas. first_seen/last_seen não viraram métricas ou pontos sintéticos.

## Videos with temporal history

45 vídeos possuem alguma observação. Distribuição por timestamps de captura:

- **1 observação — 5 vídeos:** 7, 8, 11, 17, 42.
- **2 observações — 8 vídeos:** 5, 27, 35, 38, 41, 43, 44, 45.
- **3+ observações — 32 vídeos:** 1, 2, 3, 4, 6, 9, 10, 12, 13, 14, 15, 16,
  18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 36, 37,
  39, 40.

Uma observação pode não conter determinado contador. Ter três snapshots não
significa ter três valores válidos para cada métrica.

## Products with temporal history

**Zero Product Entities aprovadas**, oito referências CANDIDATE não confirmadas.
Não foram promovidas a entidades nem usadas para merge. Os candidates 1 e 2
compartilham evidência do vídeo 3; não representam dois sinais independentes.

Coortes de candidate começam no timestamp da evidência persistida. Entidades
aprovadas futuras começam no máximo entre aprovação e evidência da ocorrência,
incluindo o timestamp real de confirmação humana. Não há retroação da aprovação.

Categorias/subcategorias/famílias são coortes retrospectivas sob a classificação
atual, explicitamente identificadas. Isso não afirma quando a categoria era conhecida
nem representa o universo do mercado.

## Average time span

Média entre a primeira e última captura dos **40 vídeos com dois ou mais timestamps**:
**12.943,968 segundos / 3,596 horas**. Os cinco vídeos com ponto único têm span NULL,
sem duração inventada. Datas são de observação, não de publicação ou compra.

## Velocity and acceleration readiness

| Target | Algum delta calculável | Duas velocidades comparáveis |
|---|---:|---:|
| VIDEO | 33 | 26 |
| CANDIDATE | 8 | 7 |
| CATEGORY | 1 | 1 |
| SUBCATEGORY | 4 | 4 |
| PRODUCT_FAMILY | 5 | 5 |
| PRODUCT_ENTITY | 0 | 0 |

Esses números indicam suficiência **matemática por alguma métrica**, incluindo
contagens locais de coorte/amostra; não confiança de tendência ou crescimento
positivo. Muitos intervalos observados são zero. Quality permanece LOW em todos
os 64 targets. A exigência mais ampla de Trend Readiness das dimensões existentes
não foi relaxada.

Velocity usa `(to-from)/delta_time`, com pelo menos dois valores válidos em
timestamps distintos. Plataforma: por hora. Coorte e amostra local: por dia.
Acceleration precisa de três pontos válidos e compara velocidades de intervalos
reais; sua magnitude usa distância entre os pontos médios dos intervalos. Tolerâncias
de STABLE ficam em política central, sem thresholds espalhados.

Valores iguais no mesmo instante colapsam com proveniência preservada; valores
conflitantes naquele instante são excluídos. Contadores em queda recebem aviso de
possível correção/remoção. Não há baseline zero, interpolação, resampling ou
carry-forward de contadores.

### Exemplo real — vídeo 3

- Comments: **1.321 → 1.327**.
- Capturas: **2026-10-21 18:07:35.321246 UTC → 2026-10-22 11:54:23.209314 UTC**.
- Período: **64.007,888 segundos / 17,780 horas**.
- Delta: **+6**, velocity **0,337458 comentários/hora**.
- Evidências: snapshots **180 e 187**, com links para as observações originais.
- Apenas duas capturas válidas desse contador: acceleration INSUFFICIENT_HISTORY.
- Momentum local GROWING, quality LOW, lifecycle EARLY_SIGNAL.

Não é uma estimativa de vendas ou de chegada de compradores.

## Creator and purchase-intent momentum

Creator momentum expõe novos criadores conhecidos, taxa de chegada observada,
concentração entre criadores identificados e single_creator_dependency. Ausência
de autor não vira diversidade fictícia. Independência continua NOT_ESTABLISHED.

Purchase Intent usa consumer signals v2 sobre comentários acumulados até cada
captura. Autor/texto repetido não adiciona intenção, e autores conhecidos são
deduplicados entre vídeos das coortes. A taxa é de **autores recém-observados na
amostra local**, não de intenção surgida naquele momento na plataforma.

Crescimento da amostra isoladamente não gera Product Momentum GROWING. A razão
COMMENT_SAMPLE_GROWTH_NOT_DEMAND_VELOCITY aparece na explicação. O engine não
confunde o ritmo da nossa coleta com demanda comercial.

## Trend quality and lifecycle

Quality considera observações, span, vídeos/criadores conhecidos, cobertura de
criador, dependência de duplicação, fontes e conflitos. Magnitude fica separada:
os testes provam quality HIGH com velocity zero e quality LOW com grande delta.

Resultado dos 64 targets:

- **61 DISCOVERED**.
- **3 EARLY_SIGNAL**: VIDEO 3 e CANDIDATE 1/2, derivados do mesmo histórico.
- **Zero EMERGING, ACCELERATING, BREAKOUT, MAINSTREAM, SATURATED ou DECLINING**
  como lifecycle atribuído.

Nos vídeos: 44 DISCOVERED e 1 EARLY_SIGNAL. Nenhum estado avançado foi forçado.
Categorias exigem pelo menos cinco vídeos, três criadores e sete dias para declarar
momentum de categoria; todas permanecem INSUFFICIENT_HISTORY nessa classificação,
mesmo quando uma contagem local tem delta calculável.

## Change-point and incremental adapters

**Change-point-ready: zero séries**. A política exige 30 pontos válidos e sete dias,
com segmento mínimo de cinco. ruptures é lazy/optional e não foi executado. Ausência
de pacote é ADAPTER_UNAVAILABLE; série curta é INSUFFICIENT_HISTORY. O resultado
futuro será evidência de possível mudança, não verdade de mercado.

O adapter River aceita `learn_one`, ignora métricas NULL e consome cada snapshot ID
uma vez. Há checkpoint JSON dos IDs consumidos. O caller deve persistir modelo e
cursor juntos. Nenhum modelo River foi treinado nesta sprint e não foram criados
dados artificiais de treinamento.

## Dashboard and future collection

Seção **TREND** no Intelligence Core, com coverage, observações, span, velocity,
acceleration, creator momentum, intenção amostral, lifecycle, quality e razões.
Cada delta mostra from/to, período e evidence IDs. Insuficiência aparece como
“Ainda precisamos de mais observações.” Não há gráfico com pontos inventados.

GET `/api/trend-history` lista targets; `target_type` e `target_id` selecionam uma
série. GET `/api/intelligence-core` inclui o histórico dos 45 vídeos. Essas leituras
não importam snapshots nem enfileiram coleta.

Smoke local: três endpoints HTTP 200. Overview temporal em 0,080s, detalhe do
vídeo 3 em 0,006s e Core completo em 2,923s, nesta máquina durante a validação.
Identity continua **0 AUTO / 6 REVIEW / 39 UNRESOLVED**.

Contrato futuro: `record_trend_snapshot(...)`, documentado em
`docs/TREND_HISTORY.md`. O enrichment só precisará fornecer timestamp real,
source key, métricas observadas e coverage; não conhece fórmulas do engine.
Nenhuma chamada ao coletor/runtime de navegador foi adicionada agora.

## Preservation

Checkpoint prévio ao código: `checkpoint.db`. Verificação em `results.json`:
68 tabelas anteriores comparadas; 66 idênticas. Somente events/system_state têm
atividade operacional permitida. Todos os eventos antigos estão preservados.
browser_security_stop e browser_security_history são idênticos ao checkpoint.

Gold, candidates, categorias, evidências, dimensões anteriores, decisões, entidades,
assets, embeddings, índice e filas permanecem iguais. Backend reiniciado pelo
Dev Control; nenhuma operação Chrome/extensão/TikTok foi executada.

## Tests

Regressão completa: **435 testes Python passaram** (sete avisos de depreciação
existentes; zero falhas), **124 testes Node/dashboard passaram** (zero falhas/skips).
Python task `89959fa2f43e4d3493e09d1023a495fb`; Node task
`c2ce6cba356b4744b2e1108f74bd8860`. Referências e estado dos runners em `tests.json`.
Adicionados 23 casos Python e um teste comportamental Node/dashboard cobrindo:

- Idempotência, aliases de timezone, NULL e zero observado.
- Rejeição de NaN/Infinity/negativos/labels e correções silenciosas de provenance.
- Dois pontos para velocity, três para acceleration, intervalos reais e conflitos.
- Creator/intent momentum, amostra local versus demanda, lifecycle conservador.
- Qualidade independente de magnitude e adapters curtos/incrementais.
- Parser de métricas persistidas, ausência de first_seen como observação.
- Zero rede, isolamento de Gold/estado de negócio e security stop preservado.
- Aprovação humana não retroativa e ausência de carry-forward de contador.
- UI explica intervalos, limitações e qualidade sem fabricar gráfico.

## Files changed

`app/trend_history.py`, `config/trend_history.json`, `scripts/trend_history.py`,
`docs/TREND_HISTORY.md`, `tests/test_trend_history.py`,
`tests/trend-history.test.cjs`; integração aditiva em `app/db.py`,
`app/intelligence_core.py`, `app/intelligence_api.py` e nos dois arquivos existentes
`app/static/intelligence-core.html`/`.js`. Artefatos desta pasta contêm checkpoint,
resultados, smoke e relatório. Nenhuma dependência pesada nova é obrigatória.

## Limitations and next data needed

Precisamos de capturas legítimas futuras do **mesmo contador do mesmo vídeo** em
horários distintos, idealmente além de 24–48h, com precisão/proveniência consistentes.
Precisamos também de mais criadores identificados, vídeos distintos do mesmo produto
aprovado, amostras deduplicadas estáveis e cobertura suficiente de categoria.

O engine não conhece publicação, bots, compras reais, independência de criadores ou
atividade não amostrada. Coortes atuais não são mercado. Um delta zero em contador
arredondado não prova ausência de atividade. Um contador decrescente pode ser uma
correção, não perda de interesse. Nenhum score final foi criado.

Próxima etapa: integrar o contrato ao enrichment somente numa sprint autorizada
com sessão saudável e security stop resolvido legitimamente; até lá, manter o latch
e usar importação offline/local. Não executar coleta agora para preencher lacunas.
