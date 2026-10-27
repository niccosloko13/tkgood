# BABI — Safe Collection Recovery v1

**Retomada em produção não autorizada pelo estado observado: UNKNOWN.**
O modo seguro foi implementado e validado com fixtures locais. Nenhuma query
TikTok foi executada, nenhuma aba foi aberta/navegada/recarregada e o security
stop não foi liberado. Sem commit.

## Initial stop state

- Stop ativo: `HTTP 403: https://www.tiktok.com/`.
- Incidente: `2026-10-23T16:23:11.456Z`.
- Companion conectado, heartbeat recente.
- Chrome/Companion reportaram **zero abas TikTok**, URL vazia, sem DOM carregado,
  sessão unconfirmed e nenhuma evidência de conta.
- A failed URL histórica de vídeo continua preservada no histórico.
- Checkpoint anterior às alterações: `checkpoint.db`; estado inicial em
  `initial-state.json`.

## Health check result

Implementado **SAFE_RECOVERY_CHECK**, que consome apenas os heartbeats PH_SIGNALS
do Companion. Não é um comando de navegação e não abre, recarrega, clica ou rola.

HEALTHY exige dois heartbeats reais distintos após a solicitação, mesmo tab/URL,
Companion provisionado/build correspondente, heartbeat com menos de 15s, DOM
complete, home/search HTTPS legítima e conta confirmada por profile/avatar da
própria conta mais inbox. Following e texto genérico não são usados.

Estados finais: HEALTHY / UNKNOWN / BLOCKED / CHALLENGE. PENDING é apenas a espera
limitada por amostras diagnósticas. UNKNOWN nunca permite coleta.

Foram feitos três checks passivos antes/depois de manutenção local, todos UNKNOWN;
nenhum tentou navegar ou repetir uma request TikTok. Último check:

`c92e25864ad212d9269f43432ce973ea`

| Evidência | Resultado real |
|---|---|
| companion_connected | true |
| heartbeat_fresh | true |
| document_ready | false |
| current_url | vazia |
| tab_id | NULL |
| page_status | unknown |
| account_signals | [] |
| session | unconfirmed |
| build_matches | true |
| health state | UNKNOWN |

Ausência de indicadores atuais de challenge/403 não é prova de página saudável:
neste caso não existe documento de aba a validar. Não foi registrado novo 403.

## Whether stop was released

**Não.** Nenhuma chamada ao endpoint de release foi feita em produção.

A liberação é uma ação separada, autenticada pelo controle local e com declaração
explícita de revisão do operador. Revalida freshness, conta, rota, tab, build e
incidente inalterado. Salva released_at, validated_url, validation_evidence e
previous_incident no registro/histórico. Heartbeat, check, captura e dashboard não
invocam release automaticamente.

Após eventual release válido, um guard estreito continua bloqueando comandos
gerais, night discovery e enrichment. Somente batches explícitos limitados passam.

## Query executed or not

**Não executada.** Stage 1 e Stage 2 não foram iniciados. Nenhum batch foi criado.

| Medida de produção desta sprint | Resultado |
|---|---:|
| Queries | 0 |
| Scrolls | 0 |
| Videos seen/captured | 0 |
| New videos | 0 |
| New search observations | 0 |
| Trend snapshots created | 0 |
| Video detail / comments / creator profile | 0 / 0 / 0 |
| Engagement | 0 |

Permanecem 45 vídeos e 392 snapshots temporais existentes. Nada foi preenchido
artificialmente para simular recuperação ou captura.

## Bounded collection path

Stage 1 está implementado para **uma query já observada**, um comando semântico
READ_SEARCH_RESULTS com opções fixas, até dez resultados, zero scroll e uma única
leitura de cards. Navegação, quando autorizada após release, usa somente a aba
validada existente. Não há abertura de Chrome/perfil/aba adicional.

O worker exige capability `safe_collection_version=v1`, vincula tab/URL, espera
readiness por status/PH_SIGNALS e realiza uma única leitura limitada. UNKNOWN,
empty viewport, erro de transporte ou block encerram a tentativa sem recaptura.
Readiness fica limitada a 35s, dentro do timeout existente do comando.

O backend revalida ownership, latch, budget/runtime e limite do payload antes de
persistir. Após captura salva, Stage 1 vira SUCCEEDED com
CAPTURE_COMPLETED_STOP. Resultados repetidos não duplicam observações. Falhas e
timeouts são terminais e não reenfileiram a query. Latch bloqueia o dispatcher.

Stage 2 só pode ser explicitamente solicitado após Stage 1 bem-sucedido da mesma
validação. Até cinco queries únicas conhecidas, 30 vídeos novos e 180s por batch;
cada viewport tem até dez resultados ou o saldo de vídeos novos. Há apenas uma
tentativa de cada stage por validação. Stage 2 pausa após cada captura; `next`
precisa de nova ação explícita e nova saúde atual. Não há loop automático.

## Pipeline validation

**Validada offline com fixtures; não comprovada com nova coleta em produção.**

- Usa o save_capture/dedup já existente.
- Cada observação de search persistida chama record_trend_snapshot pelo hook
  central do repositório, na mesma transação, sem fórmulas de trend no collector.
- Métricas ausentes continuam NULL; não há download de imagem/CDN.
- Category classification é restrita aos IDs da captura.
- Jobs existentes de identidade são enfileirados; providers/enrichment não rodam.
- Reenvio do mesmo resultado é idempotente e não duplica rows/snapshots/jobs.
- Teste de dedup confirmou captura de vídeo já conhecido, observação nova,
  snapshot temporal, category record, job de identidade e parada após a captura.
- Fixture com 25 cards visíveis foi limitada a dez, sem scroll/click/engagement.
- Challenge/403/Access Denied/CAPTCHA interrompem a leitura sem retry e persistem
  incidente/batch BLOCKED; qualquer comando pendente é interrompido.

## Dashboard

COLLECTION HEALTH no Intelligence Core mostra Companion, Session, Page, Security
Stop, Last safe validation, último check/coleta, New videos e Last stop reason.
GET `/api/collection-health` é local/read-only. Não expõe token nem botão de
auto-release. O dashboard não inicia coleta para obter um estado mais favorável.

## Maintenance and errors

Dev Control reiniciou somente o backend e recarregou a extensão para disponibilizar
o caminho limitado. As duas operações de reload da extensão reportaram
**refreshed TikTok tabs: 0**, mantendo o latch. Build final carregado:
`d2b455eaa25cef67`. Não houve bootstrap de outro Chrome nem alteração de profile,
cookies ou login. Manutenção não foi usada para validar uma página inexistente.

A regressão inicial detectou duas incompatibilidades, corrigidas sem reduzir testes:

1. Heartbeat legado passou a receber capability extra. A capability agora acompanha
   apenas o build identificado, preservando o contrato legado e impedindo uso do
   caminho limitado por build antigo.
2. Fixtures/legado podem ter timestamps sem timezone. O hook preserva esses dados
   e registra TREND_SKIPPED_AMBIGUOUS_TIMESTAMP; não inventa UTC e não quebra a
   persistência existente. Capturas normais usam timestamp real timezone-aware.

Não há regressão conhecida pendente. O impedimento atual é operacional: nenhuma
aba TikTok aberta manualmente com evidência saudável.

## Final security state and preservation

Stop e histórico são **exatamente iguais ao checkpoint**. Setenta tabelas anteriores
foram comparadas: 67 idênticas. As alterações esperadas são em events, system_state
e dev_commands pela manutenção/heartbeat. Todos os eventos anteriores permanecem.

Gold, candidatos, Identity, categorias, evidências, reviews, assets, embeddings,
índice, dimensões e histórico temporal foram preservados. A validação com fixtures
usa bancos temporários; não inseriu dados falsos no banco de produção.

Evidências completas: `verification.json`, `initial-state.json` e `tests.json`.

## Test results

Regressão completa final: **455 testes Python passaram**, sete avisos de depreciação
existentes; **128 testes Node/dashboard passaram**, zero falhas/skips. Python task
`73bcd72034b04b53938971759c837e1a`; Node task `c52a38b8dd274749a92f0bab78d2d97f`.
Resultados registrados em `tests.json`. Inclui os testes existentes,
20 casos Python novos e quatro casos Node novos para estados de saúde, ausência
de unlatch automático, freshness/incidente, hard limits, Stage 2, runtime/timeout,
dedup, trend hook, category/jobs, parada, zero engagement e segurança.

Fixtures comprovaram o caminho; a captura real continua **não executada**.

## Files changed

Novos: `app/safe_collection.py`, `app/safe_collection_api.py`,
`scripts/safe_collection.py`, `docs/SAFE_COLLECTION_RECOVERY.md`,
`tests/test_safe_collection.py`, `tests/safe-collection.test.cjs` e artefatos desta
pasta. Integrações nos arquivos existentes de DB, main/schemas/browser_safety,
observations/trend_history/Intelligence Core, UI do Core e no bounded reader do
Companion (`background.js`, `content.js`, `search_results.js`). Nenhuma alteração
de Gold, taxonomy, detector, Decision Gate, Identity Resolver ou providers.

## Next action

O usuário deve abrir manualmente uma home/search legítima no Chrome existente.
Depois executar o check passivo:

```
.\.venv\Scripts\python.exe scripts/safe_collection.py check
```

Somente se HEALTHY, inspecionar a evidência e realizar a liberação explícita,
seguida de Stage 1 com uma query conhecida. UNKNOWN/BLOCKED/CHALLENGE mantêm a
coleta parada. Não tentar resolver bloqueio com reloads, outro perfil ou bypass.

Operação e contrato detalhados em `docs/SAFE_COLLECTION_RECOVERY.md`.

## Validação atual solicitada — 2026-10-24

Check passivo `ef1972d7cf2691f25f534f7be5cf788c`: **UNKNOWN**. Backend saudável,
Companion conectado, heartbeat recente, zero abas TikTok, URL vazia, DOM ausente,
sessão unconfirmed. O inventário do perfil dedicado não encontrou processo
correspondente; não foi presumido que o perfil correto está disponível.

O opener existente (`app/chrome_launcher.py:_open_tiktok`) recusa abertura com
security_stop ativo. A exceção antiga de validate-home também não permite este
incidente da própria home. Nenhuma dessas proteções foi alterada ou contornada.
Não houve abertura de Chrome/aba, navegação, release ou Stage 1/2.

Resultado desta validação: zero resultados, novos vídeos, duplicados, observações
de search e snapshots novos. Stop histórico da home continua ativo e sem alteração.
Evidência completa: `current-session-validation.json`.

Próximo passo: disponibilizar uma home/search aberta manualmente no Chrome com o
Companion; o agente executará o check e os passos condicionais sem exigir comandos
manuais do usuário.
