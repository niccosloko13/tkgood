# Gold Set + Detection Benchmark v1

22/10/2026, sprint offline. **Infraestrutura e baseline sem revisão humana**;
nenhum label foi inventado e nenhuma qualidade do detector foi presumida.

## Revisão humana e persistência

`app/gold_set.py` e `app/gold_set_api.py` implementam uma camada separada.
Migração aditiva cria:

- `gold_video_labels`: video_id + review_version, pending/reviewed, presença
  yes/no/unclear, nomes raw/canonical, especificidade, notas, idioma, FN/FP reasons,
  reviewed_at e reviewer_type;
- `gold_candidate_reviews`: avaliação por candidate **e vídeo**, name_match
  exact/acceptable/wrong/unreviewed, força strong/weak/wrong, notas e data;
- `gold_review_history`: snapshots de alterações humanas, sem apagar revisões anteriores;
- `detection_benchmark_runs`: versões, métricas, fingerprint e relatório/snapshot do run.

Labels novos são pending com nomes/presença/especificidade null. Candidate existente,
unresolved phrase ou detection gap é apenas sugestão contextual. Não há comparação
automática de strings que gere um name_match humano. Mesma submissão humana não
duplica histórico ou altera reviewed_at; mudanças reais preservam histórico.

Qualidade → **Gold Set — revisão humana** carrega os 45 vídeos sob demanda.
Mostra caption, creator, URL, candidates, amostra/resumo de comentários, evidências,
últimas observações de busca/detail e contexto de creator já persistido.
Sem polling adicional da revisão. O formulário não é sobrescrito pelo refresh geral.
Previous/next e filtro pending preservam drafts locais; não salvam automaticamente.
Y/N/U escolhem somente presença; Ctrl+Enter e o botão **Salvar e avançar** salvam
e seguem ao próximo vídeo. Setas ←/→ navegam fora dos campos. Atalhos só atuam em
Qualidade, sem drawer aberto; letras são ignoradas ao digitar em inputs/textarea/select.
Nome, especificidade e confirmação humana nunca são preenchidos por esses atalhos.
Falha ao salvar mantém o vídeo/draft; duplo Ctrl+Enter não duplica submissões.
O filtro pending não faz o avanço pular um vídeo quando o recém-revisado sai da lista.
Salvar exige escolhas de presença/especificidade e confirmação explícita de revisão
humana. Canonical/raw names permanecem em branco até preenchimento humano.
Name match e força são revisados separadamente para cada candidate daquele vídeo.

### Review visual — atualização de apresentação em 23/10/2026

Layout desktop 45/55: área grande de mídia à esquerda e contexto à direita; no
mobile a ordem é preview/contexto/detector/comments/revisão. CTA Salvar e próximo
fixo acima da navegação inferior. Header com posição, revisados/restantes e progresso.
Decisões são controles grandes com estado selecionado forte; nomes e name match são
ocultos/desativados em NÃO, sem apagar drafts. Especificidade e confirmação humana
continuam explícitas conforme o contrato já existente; nenhuma regra de label mudou.

Mídia local segura tem prioridade; preview local usa controls/preload=none, sem
autoplay. Thumbnail HTTPS persistida só é requisitada após **clique explícito** em
Carregar imagem persistida, conforme escolha do usuário. Sem scraping, cache novo
ou download automático. Falha exibe placeholder, sem retry automático. Na ausência
de preview, placeholder Preview não armazenado e Abrir vídeo com a URL persistida.
O link Abrir no TikTok é discreto; não é acionado por testes/sprint/benchmark.
Não inferir produto pela existência do candidate ou do preview.

Até oito comentários úteis já persistidos são priorizados por menção explícita,
pergunta de nome, preço/onde comprar/link/intent. Todos continuam acessíveis em
Ver todos os comentários. Chips unresolved só preenchem **nome original como draft**
ao clicar; não preenchem canonical/presença/especificidade, não confirmam revisão e
não salvam. Isso é apresentação, sem alterar classificação/sinais/contagens do detector.

Resumo compacto usa somente dados persistidos. No vídeo1: @airlandolists, caption
Easy to remove the stains😏 #gadgets; unresolved vacuum cleaner / Mini Vacuum Cleaner;
2 menções, 30 comments sampled, buy intent3, link intent11. Quatro comentários reais
destacados: vacuum cleaner; Mini Vacuum Cleaner Price? very useful ✨;
qual nome do produto?; onde compro um desses?. Nenhum texto de exemplo foi inventado.

JSON/provenance/snapshots ficam apenas em Evidência técnica, fechado por padrão.
Benchmark fica recolhido, com aviso disponível após15 revisões; seus cálculos e
gatilhos não mudaram. Menos campos secundários na tela principal; revisão continua
na mesma área Qualidade, sem nova página/arquitetura/API/migração.

API exclusivamente local:

```
GET  /api/gold-set
GET  /api/gold-set/{video_id}
POST /api/gold-set/{video_id}/review
POST /api/gold-set/benchmark
GET  /api/gold-set/benchmark/latest
```

Review exige human_reviewed=true, review_version=gold-set-v1 e enumerações válidas.
Candidate avaliado deve estar ligado ao vídeo por evidência persistida.
Idiomas pt/en/ar/es/unknown são escolhidos pelo humano; nenhum idioma é inferido.
Uma revisão pode decidir presença e ainda deixar name_match unreviewed.

## Definições de métricas — duas leituras explícitas

Matriz **presença**, independente do nome (`presence`):

| Humano | Detector emitiu candidate no vídeo | Classe |
|---|---|---|
| yes | sim | TP de presença |
| no | sim | FP |
| yes | não | FN de presença |
| no | não | TN |

`detection_presence_correct` só responde à presença. Não identifica o nome como correto.

Resultado **principal estrito** (`primary_metric=strict_name_aware`, campos top-level
tp/fp/fn/tn/precision/recall/f1 e entidade persistida): TP exige humano=yes e pelo
menos um candidate com name_match humano exact/acceptable. FP/TN seguem a matriz.
Humano=yes sem candidate aceitável é FN estrito. Isso inclui `wrong_name` quando
há candidate mas todos os nomes foram avaliados como errados; **não é um FN de
presença**. Essa distinção permanece explícita nos dois blocos e reasons.
Humano=yes com candidate e naming ainda incompleto é excluído da matriz estrita
como pending_name_match, sem receber TP automático.

Unclear e pending review são excluídos de ambas as matrizes; não viram TN.
Um nome errado continua erro mesmo quando a presença foi detectada corretamente.
Não confundir acerto de presença com identificação aceitável.

Precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2TP/(2TP+FP+FN).
Denominador zero → null, nunca uma falsa taxa de 0% ou 100%.
`presence_detection_accuracy` = (TP+TN)/todos os casos elegíveis da matriz de presença.
`product_naming_accuracy` = exact/acceptable entre nomes de candidate-occurrences
explicitamente revisados em vídeos com humano=yes; unreviewed/unclear não entram.
Name match por vídeo agrega as decisões humanas locais; exact/acceptable tem
precedência; wrong só quando todos os nomes daquele vídeo foram avaliados como wrong.

Cobertura = vídeos da Library com algum candidate / vídeos da Library, separada
da avaliação revisada. Não é qualidade, precision, recall ou F1.
Predições representam hypotheses emitidas, incluindo eventual rejeição local posterior;
não são corrigidas pelo benchmark ou filtradas para melhorar o resultado.

Breakdown pt/en/ar/es/unknown mantém contagens reais. Taxas só aparecem com pelo
menos cinco casos elegíveis no grupo; abaixo disso são null. Esse mínimo de exibição
do benchmark não muda threshold operacional e não estabelece significância estatística.
Denominadores e exclusões continuam no relatório.

## Error analysis

FN reasons humanos: unknown_vocabulary, caption_missing, product_only_in_comments,
generic_phrase, unsupported_language, insufficient_text, normalization_failure, other.
FP reasons humanos: generic_term, wrong_context, creator_context_leak,
search_query_leak, comment_noise, other.

Se o humano não classificar a causa, relatório usa `unclassified`, sem inferir
uma causa do detection gap. `wrong_name` estrito é derivado da decisão humana de
nome errado e fica separado dos FN por ausência de candidate. Sugestões não são labels.

## Versões, runs e idempotência

Gold/review version: gold-set-v1. Protocolo: detection-benchmark-v1.
Run guarda detector_version, vocabulary_version e rules_version lidos da configuração
atual, snapshots de configurações/vocabulário, labels e predições por vídeo.
Fingerprints incluem protocolo/política, versões, inputs e configurações. Inputs iguais
reutilizam run e timestamp; labels ou predições/configs diferentes geram outro run.
Não há novo detection run nem alteração de normalization, weights ou vocabulário.
Runs iniciais de construção do protocolo foram preservados; relatório atual usa run 3.

## Baseline real atual

- Library: **45 vídeos**; revisão humana: **0/45**; pending: **45**.
- Yes **0**, no **0**, unclear **0**. Não são labels negativos: ninguém foi revisado.
- TP/FP/FN/TN estritos: **0/0/0/0** em **zero vídeos elegíveis**.
- Precision/recall/F1/presence accuracy/naming accuracy: **null / indisponíveis**.
- FN reasons: nenhum classificado. FP reasons: nenhum classificado.
- Coverage: **8/45 = 17,78%**, apenas distribuição de outputs existentes.
- 8 candidates, 9 candidate-video occurrences, 65 evidências operacionais intactas.
- Sem métricas de idioma válidas antes de labels humanos.

### Auditoria explícita dos oito candidates

| Candidate | Vídeo Library | Human product presence | Name match | Strong/weak/wrong | Notas humanas |
|---|---|---|---|---|---|
| Soap dispenser | 3 | não revisado | unreviewed | — | — |
| dish brush | 3 | não revisado | unreviewed | — | — |
| Burger Patty Maker | 9 | não revisado | unreviewed | — | — |
| fruit spinner | 10 | não revisado | unreviewed | — | — |
| long-handled floor brush | 13 | não revisado | unreviewed | — | — |
| 3 in 1 Window Cleaner | 15 | não revisado | unreviewed | — | — |
| Portable Dryer | 16 | não revisado | unreviewed | — | — |
| escova | 39 e 40 | não revisado em ambos | unreviewed | — | — |

Auditoria humana pendente, não substituída por juízo do agente. JSON inclui URLs,
captions, nomes existentes e status pendente de cada ocorrência. Corroboration ou
resolver anteriores não contam como verdade humana. Escova não recebeu label positivo
por ser conceito recorrente. Nenhum candidate foi alterado.

## Export e operação offline

```
.\.venv\Scripts\python.exe scripts/detection_benchmark.py --record
.\.venv\Scripts\python.exe scripts/detection_benchmark.py
.\.venv\Scripts\python.exe scripts/background_runner.py pytest
.\.venv\Scripts\python.exe scripts/background_runner.py node-tests
```

--record cria labels **pendentes** para vídeos sem label e persiste/reutiliza o run;
não cria revisão humana. Default é SQLite read-only e exporta avaliação atual sem run
novo. POST benchmark local também exporta. Arquivos: `data/gold_set_v1.json` e
`data/detection_benchmark_v1.json`; usam escrita temporária e substituição local.
Após cada revisão humana salva, a partir de **15 revisados**, benchmark/export
são recalculados automaticamente e marcados **PARTIAL GOLD SET**. Ao concluir todos
os vídeos (45 no corpus atual), geram **FINAL GOLD SET**, versão gold-set-v1.
Incluem reviewed/yes/no/unclear, TP/FP/FN/TN, precision/recall/F1, naming accuracy e
principais causas FN/FP. Unclear/naming pendente continuam excluídos conforme protocolo;
15 labels não garantem 15 casos elegíveis nem tornam taxas indefinidas em números.
Antes de 15, cálculo manual continua disponível. Um cálculo manual incompleto também
fica marcado PARTIAL GOLD SET; sem labels é UNREVIEWED BASELINE.

Label é commitado antes do cálculo/export. Se o relatório falhar, revisão é preservada
e a UI pede recálculo local, sem repetir automaticamente operações. Repetir a mesma
revisão/benchmark reutiliza o run quando inputs são iguais. Nenhuma amostra parcial
altera o detector, vocabulário, pesos, thresholds ou aprende produtos automaticamente.
O número 15 é apenas gatilho de relatório; não é threshold de detecção.

Backup: data/product_hunter.pre_benchmark.db. Preservação: benchmark_before/after.json
e benchmark_verification.json. Logs .runtime/logs. Backend reiniciado silenciosamente
via restart-backend; sem reload de Companion ou TikTok. Security stop HTTP403 intacto.

Limite principal: **não existe qualidade medida sem revisão humana**. Dados textuais
persistidos e thumbnails sem cache podem ser insuficientes. Sem LLM/embeddings,
novos candidates, learning, ajuste de thresholds ou melhorias do detector.
Testes/checkpoint finais em NEXT_SESSION.md. Sem navegação/engagement/commit.


## Filtros de erros no review

O Gold Set oferece Todos/Pendentes/TP/FP/FN/TN/Incerto com contagens atuais.
A categoria usa a mesma regra strict name-aware: produto humano presente com
nome aceitavel/exato e TP; sem candidate aceitavel e FN; nome ainda nao revisado
fica excluido de TP/FN. Incerto nao entra na matriz. Filtrar nao salva revisoes.
O badge FN explica a divergencia e Classificar motivo do FN abre os campos
humanos, sem selecionar nem salvar automaticamente.

review_method e opcional e humano: persisted_only, video_opened, lens_assisted.
Motivos FN adicionais: visual_only, visual_helped, generic_caption,
missing_enrichment. Motivos legados permanecem aceitos e inalterados.
Todos dependem de escolha explicita e confirmacao/Salvar; a interface nao abre
TikTok ou Lens para inferir o metodo. Migracao apenas adiciona coluna nullable;
gold-set-v1 e formulas do benchmark permanecem iguais. Relatorios anteriores
permanecem snapshots; proximo save/calculo usa o fluxo de benchmark existente.
