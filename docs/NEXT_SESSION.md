# Visual Identity Completion V1 — 2026-10-23

Pipeline visual real integrado ao core existente, sem mudar o Decision Gate.
1 asset local processado; provider automático disponível via OpenRouter configurado.
Nomes gerados sem caption/comentários/Gold no prompt inicial.
Hipóteses ativas: Window vacuum cleaner; alternativa Glass cleaner device.
3 sugestões históricas preservadas; reruns do mesmo provider não são votos independentes.
OpenCLIP/FAISS participam: imagem cacheada, embeddings dos nomes, top-3 tipado.
2 fontes públicas atuais (Bosch/Kärcher) corroboram família, não SKU exato.
Lens automático indisponível; LENS_ASSISTED_REQUIRED continua explícito.
AUTO 0 / REVIEW 6 / UNRESOLVED 39; nenhuma identidade/label humano forçado.
Gold, fontes originais e security stop preservados. ZERO TikTok e ZERO commit.
Regressão final: 380 Python + 122 Node/dashboard passaram.
Ver artifacts/visual-identity-completion/REPORT.md e docs/VISUAL_IDENTITY_COMPLETION.md.
Precisão física e revisão como exceção ainda não demonstradas com apenas uma imagem.

---

# Intelligence Core activation — 2026-10-23

Core existente ativado: AUTO 0 / REVIEW 6 / UNRESOLVED 39.
Vídeo 3: REVIEW_TEXT_COMPOSITE_PRODUCT, sem depender de imagem.
Vídeo 1: Mini Vacuum Cleaner como hipótese de comentário, sem confirmação visual.
OpenCLIP real em CPU: asset 1, 512 dimensões, cold 12,61 s incluindo carga;
segunda execução e novos processos usam cache. 1 image + 9 text embeddings.
FAISS: 8 CANDIDATE_REFERENCE reais; 0 Entities/confirmed occurrences.
Não interpretar cosine/top-k como identidade. Lens: LENS_ASSISTED_REQUIRED.
Purchase Intent medido em 6 vídeos; vídeo 18 tem identity UNRESOLVED e intent STRONG.
Modelo continua lazy; worker único limitado usa camada background_runner existente,
cooldown para recursos e unload idle. Nenhum acesso TikTok ou clear do security stop.
55 tabelas-fonte, Gold, assets e evidências preservados; decisões antigas intactas.
Regressão final: 364 Python + 121 Node/dashboard passaram, sem reduzir coverage.
Ver artifacts/core-activation/REPORT.md, first-pilot.json e verification.json.
Somente 1 imagem local existe; piloto visual adicional precisa de outros uploads.
Sem commit.

---

# Intelligence Core consolidation — 2026-10-23

Core local em `/intelligence-core`. AUTO 0, REVIEW 0, UNRESOLVED 45.
45 vídeos, 8 candidates, 1 imagem local, 0 propostas visuais/web, 0 Entities.
Modelo oficial OpenCLIP instalado/verificado, mas inferência recusada por RAM.
FAISS ativo vazio; nenhum Candidate/Gold foi convertido em Entity.
Security stop/home403 e histórico preservados. ZERO acesso TikTok nesta sprint.
338 testes Python e 120 Node passaram. Nenhum commit.
A sprint é parcial: matching real e redução de revisão com precisão ainda não demonstrados.
Ver artifacts/intelligence-core-consolidation/REPORT.md e docs/INTELLIGENCE_CORE.md.
Próximo passo útil: folga real de RAM + evidências locais/assistidas; sem limpar latch.

---

# Checkpoint: Local Visual Assets + Assisted Identification (2026-10-23)

STOP TikTok/home403 continua ativo. ZERO TikTok/CDN requests,clear,discovery,
Chrome automation,Gold/Candidate mutation,supplier scraping ou commit.
Usuario confirmou: vai adicionar imagens reais PELO REVIEW. Nao gerar frames
falsos nem baixar CDN para preencher a fila. Relatorio atual:
artifacts/local-visual-assets/REPORT.md;baseline before.json/checkpoint.db.

Upload manual,file picker e drag/drop na secao visual. PNG/JPG/JPEG/WebP,
MIME/decoder/dimensoes/hash validos,10MiB,8192px/lado,20M pixels. Pillow12.3.0
instalado na .venv existente e pinado em requirements.txt. Sem multipart novo;
POST binario local limitado por Content-Length e chunks. Arquivos em
data/visual_assets/{video_id}/{sha256}.{ext};thumbnail_url permanece intacta.
Source manual_upload/imported_asset;future_capture so contrato e bloqueado sob
stop. Dedup por video/hash nao regrava arquivo valido. Asset legado reenviado
mantem id,arquiva proveniencia antiga e recebe caminho/dimensoes gerenciados.
VisualProductEvidence NAO reconstruido.

IDENTIFICAR PRODUTO prepara pacote local/hash/contexto;nao envia ao provider.
Piloto assistido HIGH+Gold:FN4,5,6,11,12,14;depoisunclear2. Outros HIGH podem
receber upload,mas nao ha expansao automatica de identificacao. Lensmanual:
downloadlocal+linknormalGoogle+formnome/url/source/listing_title/observed_at/notes;
resultado google_lens_assisted/suggested. Referenciasweb guardam domain e flags
humanas de match/compatibilidade/independencia;nao buscam preco/fornecedor.

Review separado em TEXT,VISUAL,WEB CONFIRMATION,FINAL HYPOTHESIS. Canonical e
aliases apenas sugeridos a partir de nomes observados,com proveniencia;nao
inventar equivalencia semantica. Imagem nova nao herda proposta/avaliacao da
anterior;drafts porvideo+hash;uploadatrasado nao troca review atual. Gold comparison
ehelpfulness exigem acaohumana separada,sem alterarlabels originais.

Na entrega:0 assets reais fornecidos,0 HIGH comimagem,14 restantes;Gold FNtested0,
helpful0/wrong0;7 itens do piloto aindaunclear. Zeros nao medem performance.
Testes usam imagens/bancos temporarios apenas. Suitefinal/logIDs emtest-results.json
eREPORT. API/dashboardlocal carregados somente porrestart-backend viaDevControl;
extensao/Chrome nao recarregados. Documentacao:docs/LOCAL_VISUAL_ASSETS.md.
Proximo passo:usuario adicionarimagem noFN4 e seguir fila;sem retomarTikTok.

Historico abaixo preservado.

# Checkpoint: Visual Product Identification v1 (2026-10-23)

Security stop da home permanece ativo e intacto. ZERO TikTok/CDN requests,
navigation, Chrome automation, clear, discovery, supplier scraping ou commit.
Internet voltou, mas isso NAO revoga o bloqueio. Trabalho local/assistido apenas.

Relatorio:artifacts/visual-identification/REPORT.md. Backup:checkpoint.db;
baseline:before.json. Piloto1 registrou exatamente14 HIGH,0 imagens locais
acessiveis,14 visual_unavailable,0 provider calls,0 sugestoes/aceitacoes/rejeicoes.
Todos HIGH so possuem URLs p16/p19-common-sign.tiktokcdn.com;nenhuma imagem
local associada foi encontrada e nenhum CDN foi requisitado. Nenhum MEDIUM.
Gold15 comparados offline,0 avaliaveis;match rate null;ganho nos9FN NAO medido.
Nao interpretar zeros como desempenho ruim da visao. Nao inventar nomes.

VisualSearchProvider possui adapters vision_model/web_image_search/
google_lens_assisted ASSISTIDOS,sem integracao remota configurada ou workaround.
VisualProductEvidence recebeu colunas aditivas,sem alterar legado. Novas propostas
exigem imagem persistida validada+SHA256 atual e comecam suggested. Decisoes
accepted/rejected/unclear exigem humano e historico;nao criam Product Entity,
candidate,Gold label ou supplier listing. Evidencia web posterior guarda snapshots
de title/url/source/observed_at/match_reason,com compatibilidade/independencia
explicitamente revisadas;URLs nao sao requisitadas pelo backend.

Contextos completos em high-review-items.json. UI VISUAL IDENTIFICATION dentro
do review e filaHIGH em Videos. UI nunca carrega thumbnailCDN no novo painel;
imagem local via endpoint validado. Arquitetura/limites:docs/VISUAL_IDENTIFICATION.md.
Sources locais somente data/visual-images ou data/media;sem busca em cache/cookies.
Nao usar arquivos/imagens de outros videos como se fossem evidencia do item.
Associação de imagem real e sugestoes assistidas futuras podem ser feitas sem
navegar TikTok. Sem imagens,nenhuma inferencia visual e emitida.

Suite completa e logs finais em REPORT/test-results.json. Backend restart somente
por devctl restart-backend;sem reload extensao/aba. Runtime Chrome/Companion,
Gold/benchmark,evidence/candidates/classifier/taxonomy/resolver e stop preservados.
Script visual_identification_report.py sem --run-pilot somente exporta estado;
--run-pilot nao cria segundo piloto inicial se ja existir registro.

Historico abaixo preservado.

# Checkpoint: Offline Intelligence (2026-10-23)

NOVO HTTP 403 NA HOME continua ativo. ZERO TikTok navigation/requests, retry,
clearance, Chrome automation ou Computer Use nesta missao. Trabalho somente local.
Relatorio: artifacts/offline-intelligence/REPORT.md; checkpoint.db/before.json;
auditoria detalhada audit.json e verification.json. Sem commit/staging.

45 videos preservados:9 classified (Casa8/Eletronicos1),36 unclassified.
Unclassified grupos primarios A4/B8/C12/D0/E0/F12; tags podem sobrepor.
Diagnostico nao atribui categorias nem labels. Classifier/taxonomy/detector intactos.
Alertas de categoria:1 comments/unresolved e confidence0.5;3 Banheiro nao provado;
40 termo amplo limpeza. Nenhuma correcao humana inferida.

Visual queue V2:37 sem candidate,14 HIGH/12 MEDIUM/11 LOW; LOW inclui preview
ausente/dados fracos. Thumbnail e so referencia;nenhuma imagem foi requisitada.
Gold15 reviews:TP5/FN9/unclear1;recall5/14=35.71%. Causas FN sao diagnosticos
separados,nao campos humanos. Vacuum cleaner/Mini Vacuum Cleaner continuam
pending reviewable suggestions,fora do vocabulario aprovado;nao foram rejeitadas
por humano. Nenhum candidate/vocabulario/label/benchmark run novo.

Historico:home gadgets unica query observada,167 aparicoes/45 unicos/122 repetidas;
73.05% duplicate por observacoes. Nao confundir com taxa por discovery session.
Planner offline sugere home organization;nenhuma execucao real.
Novo painel textual em Overview/Videos e GET /api/offline-intelligence sao locais
e read-only. Filtros rapidos Casa/Cozinha/Limpeza/Organizacao/Unclassified/Visual/
Candidate ausente/Unresolved. Sem requests de imagem ou links externos no painel.
SupplierListingEvidence e contrato Pydantic somente;schema exportado,sem scraping,
provider,tabela nova,product entity ou matching automatico.
Arquitetura:docs/PRODUCT_IDENTIFICATION_PIPELINE.md.

277 Python +114 Node/dashboard passed;4 warnings Python antigos. API/asset200 OK.
Backend reiniciado somente por devctl restart-backend,sem reload da extensao/aba.
Extensao e controles de browser byte-a-byte preservados. Todas tabelas de negocio,
Gold,benchmark,evidence,resolver,enrichment/queries preservadas. Security stop e
historico preservados. Volateis events/system_state podem mudar por heartbeat.
Proximo passo humano:revisar offline os14 HIGH e alertas1/3/40;nenhuma retomada
TikTok automatica. Qualquer etapa online:blocked_by_security_stop.

Historico abaixo preservado.

# Checkpoint: Companion recovery (2026-10-23)

User explicitly authorized fixed-home recovery after reviewing the old video 403;
no Computer Use for this recovery. See artifacts/discovery-recovery/REPORT.md.
Database backup and full table/source hashes: artifacts/discovery-recovery/checkpoint.json.

Backend healthy. The dedicated chrome-tiktok-main profile has no live Chrome
process. Companion is registered in that profile's Secure Preferences, but not
in the running default Chrome profile. Last heartbeat is still
2026-10-22T14:38:35.944786+00:00. devctl reload-extension refused to create another
Chrome. No TikTok navigation, latch clearing, smoke, discovery or enrichment.

Code fixes: Dev Control is no longer starved by security latch; ordinary reload
never revisits failed URLs; explicit validate-home only; controlled, incident-bound
clearance after fresh authenticated healthy home; account-specific visible DOM
evidence replaces generic Following text; connection states separated. Night
adapter readiness key fixed (ready_state). No taxonomy/classifier/detector changes.
Code is tested locally; new Companion build NOT verified loaded in real Chrome.

Preserve existing authenticated profile/session. Restore the Companion-bearing
profile legitimately, without changing cookies/login, then reload through devctl.
Do not clear the stop merely to run discovery. Home first; new challenge stops.
Smoke: one SEARCH/detail/comments/creator. Discovery caps: 3 sessions,20 new/session,
50 total new. Existing runner default caps are broader: do not start it blindly.
Visual queue is a JSON view of 2 HISTORICAL videos, not new discovery or Lens output.
Full final test counts and exact task IDs are in the report. No commit/staging.

Historical checkpoints below remain preserved.

# Checkpoint: Discovery + Category Intelligence v1

Missao do arquivo anexado implementada localmente. Ler artifacts/night-discovery/REPORT.md
e docs/CATEGORY_INTELLIGENCE.md. SECURITY STOP HTTP403 continua ativo:ZERO navegacao,
ZERO commands TikTok novos, ZERO enrichment real. Nao limpar latch para validar.
Library45,candidates8,evidence65,unresolved2;Gold15 reviews TP5 FP0 FN9 TN0 intactos.
Classificacao:Casa8,Eletronicos1,unclassified36. Planner atual:home organization.
Runner1 parou security_stop antes de submit;0 novas sessoes/novos videos. Limites
12 sessoes,25 videos/sessao,200 novos total,3600s;readiness/cooldown/polling bounded.
Restart backend deixa progresso interrupted para resume explicito;Chrome/aba intocados.
Novas tabelas so aditivas;before/after snapshots data/category_mission_{before,after}.json.
Hashes todas tabelas antigas de negocio iguais;events/system_state/sqlite_sequence
mudaram por devctl/heartbeat. Bridge commands/configs antigos/security iguais.
Categoria nao confirma produto. Query/bio sozinhas nao classificam. Gold labels nunca
sao input do classifier. Human review de categoria e visual separados,sem auto-label.
UI filtros em Videos,overview compacto;PT/ar/RTL;registrovisualmanual sem abrir Lens.
Prioridade nova usada na fila existente sem rodar lote;preferencia videos novos preservada.
235 Python +103 Node passed;logs tasks01128dd77c6549d6b30ba248815af881 e
02dc3c673df24b5881381435bdd0e410. QA local isolado .runtime/category-visual.
Backend-only restart taska4e301d7e6824092ac10883163807405 SUCCEEDED,nao reload-all.
Pendencia real:validacao SEARCH/discovery ao vivo bloqueada por403;sem workaround.
Nao houve nova coleta;nao afirmar que runner coletou200videos. Manual categoria/visual
aguardam escolhas humanas. Tests/test_enrichment.py permanece reconstruido,original
exato indisponivel no Git. Preservar cobertura. Sem commit/staging/engagement.

---

# Atualizacao: exportacao do Gold Set

Botao Exportar revisoes (.zip) junto aos filtros, PT-BR/ar-EG. GET /api/gold-set/export
retorna download com todas as revisoes SALVAS (independente do filtro), historico
humano, CSV UTF8 para planilha, benchmark mais recente e historico dos benchmarks.
Nao exporta drafts nao salvos; nao recalcula benchmark nem escreve no banco.
JSON preserva texto original; CSV neutraliza formulas de planilha. Sem TikTok.
Validado HTTP real local:15 revisoes,4 arquivos ZIP.3 testes Python focados e13
Node UI passaram;teste compara dump do banco antes/depois da exportacao.
Backend restart devctl silencioso0d5366a7e872455496f9cd2070829087 SUCCEEDED.
Security stop preservado;sem navegacao/engagement/commit. diff --check passou.

---

# Checkpoint atual: Gold Set benchmark error filters

23/10/2026. Filtros no mesmo review: Todos, Pendentes, TP, FP, FN, TN, Incerto,
com contagens derivadas dos labels atuais pela mesma elegibilidade strict name-aware
ja usada no benchmark. Nome humano ainda nao revisado fica excluido de TP/FN,
nao e automaticamente considerado errado. Nenhuma formula alterada.

Estado REAL:45 videos;15 revisados (14 yes,0 no,1 unclear);30 pending;
TP5,FP0,FN9,TN0. FN video IDs internos:1,4,5,6,7,8,11,12,14.
Badge FN + explicacao + Classificar motivo do FN abre campos humanos existentes.
Salvar/Salvar e proximo e confirmacao humana continuam obrigatorios; clicar no
filtro ou classificar nao grava nada. Sem rotulo/motivo/metodo inferido.

Migracao aditiva: gold_video_labels.review_method nullable, valores persisted_only,
video_opened,lens_assisted. Omissao do metodo por cliente antigo preserva valor.
Novos FN reasons visual_only,visual_helped,generic_caption,missing_enrichment;
demais motivos solicitados e antigos continuam aceitos sem remapeamento destrutivo.
Nenhum metodo foi preenchido no banco real. History e idempotencia preservados.

Arquivos deste passo:app/gold_set.py,app/gold_set_api.py,app/static/index.html,
tests/test_gold_filters.py,tests/gold-set-ui.test.cjs,docs/DETECTION_BENCHMARK.md,
este checkpoint. Backend reiniciado APENAS por devctl restart-backend silencioso
(task cf4a98ba6f904f62b117e2204fa23b70,SUCCEEDED). Nao usar reload-all:security stop
HTTP403 continua ativo. Nenhuma navegacao/TikTok/Companion command/enrichment.

Suite completa:227 Python passed (4 warnings antigos),101 Node/dashboard passed.
Tasks logs .runtime/logs/task-9bd55a24b7f84db9813d1c8a73dcb83f.* e
.runtime/logs/task-917d8719053542d293807e8de2cfa866.*. PT-BR/ar-EG,desktop/mobile
validado em fixture file:// isolada Chromium headless;0 requests externas,
sem overflow,technical details fechado,thumbnail remota sem src automatico.
Screens .runtime/gold-visual/. Nao foi navegador TikTok/persistente do usuario.

data/gold_filters_before.json e gold_filters_after.json:projecao dos labels
preexistentes tem hash identico;somente coluna nullable adicionada. Benchmark runs,
candidates,evidence e demais dados de negocio inalterados. events/system_state/
sqlite_sequence mudaram pelo restart/heartbeat;bridge_commands identicos,
security stop identico,configs e testes legados identicos. git diff --check passou;
stat/status revisados;workspace sujo anterior preservado. Sem commit/staging.

Limitacao:contagens sao dos labels correntes;benchmark salvo permanece snapshot
ate proximo save/calculo ja existente. Nao foram criadas classificacoes humanas.
Tests/test_enrichment.py continua RECONSTRUIDO;original exato indisponivel no Git.
Nao apresentar como recuperacao exata. Checkpoints historicos abaixo.

---

# Checkpoint atual: Gold Set review visual (somente UI)

23/10/2026. Redesign funcional concluido; sem nova arquitetura/backend/API/migracao.
Nenhuma alteracao em gold-set-v1, benchmark, labels, detector, regras, configs,
candidates, unresolved, banco ou security stop. Sem commit/staging/TikTok navigation.

Qualidade agora prioriza GOLD SET REVIEW; diagnostico antigo de captura recolhido.
Desktop45/55: preview grande e contexto. Mobile: preview/contexto/detector/comments/
review, CTA Salvar e proximo fixo acima da barra de navegacao. Cabecalho com
posicao/progresso/revisados/restantes, anterior/proximo/pending filter.
Caption e hashtags legiveis; creator e Abrir no TikTok discreto usando URL persistida.
Apenas usuario pode acionar esse link, nunca sprint/testes.

Midia: local segura primeiro; preview local com preload=none/sem autoplay. Usuario
ESCOLHEU carregar thumbnail_url remota somente ao clicar, sem download automatico.
Botao Carregar imagem persistida requisita so a URL ja existente; sem scraping/cache
ou retry automatico. Se falhar, placeholder Preview nao armazenado/Imagem indisponivel.
Nenhuma imagem remota foi requisitada nesta validacao; validade/expiracao da URL nao
foi testada. Area visual existe mesmo sem midia, com Abrir video manual.

Detector/candidates/unresolved em card limpo, chips Usar como rascunho preenchem
somente nome original mediante clique. Nenhum campo humano ou canonical inferido,
nenhum save automatico. Ate8 comentarios relevantes, todos acessiveis em details.
Video1 REAL @airlandolists: Easy to remove the stains + #gadgets; unresolved vacuum
cleaner / Mini Vacuum Cleaner; quatro exemplos pedidos existem de fato nos dados.
Resumo real:2 product mentions,30 comments sampled,3 buy intent,11 link intent.
Fonte apenas persistida; ranking local de comments e helper de apresentacao.

SUA REVISAO: grandes botoes sem radios pequenos visiveis, estado selecionado forte.
SIM ativa nomes/name match; NAO oculta/desativa nomes preservando drafts; INCERTO
permite nome opcional. Especificidade/confirmacao humana continuam explicitas
(conforme API existente); nao houve auto label ou mudanca de validacao.
Y/N/U, Ctrl+Enter, setas, pending filter e save-next preservados.
JSON/provenance/source snapshots apenas em Evidencia tecnica fechado por padrao.
Benchmark recolhido; aviso apos15; regra automatica15/45 anterior INALTERADA.

Validacao:225 Python passed (4 warnings existentes),100 Node/dashboard passed.
Python taskd8074cb16aa54cf0a72cdd5d0d28ff37; Node final2a4adbd0c5634442b1afba66f69515c4.
Visual real local em Chromium headless ISOLADO via dependencia QA ja existente
.runtime/ui-test/node_modules/playwright, somente file://fixture. Nunca Playwright
em TikTok ou perfil Chrome do usuario. Todas requests externas bloqueadas;0 tentadas.
PT-BR/ar-EG em1440x1000 e390x844: sem overflow,0 JSON visivel, details tecnicos fechados,
CTA mobile fixed, atalhos/chips sem inferir confirmacao. Screenshots inspecionados.
Nenhum Chrome persistente/Companion reiniciado; HTML e lido do arquivo pelo backend.
Nao foi necessario restart, reload de browser ou novo servidor.

Artefatos visuais .runtime/gold-visual/{pt-BR,ar-EG}-{1440,390}.png e validation.json.
Fixture REAL tests/fixtures/gold-review-video-1.json (apenas dados persistidos, sem
labels artificiais). Testes novos/ajustados em tests/gold-set-ui.test.cjs,11 casos.
Arquivos de produto alterados SOMENTE app/static/index.html; helpers de UI no mesmo
arquivo. Docs DETECTION_BENCHMARK.md e este checkpoint atualizados.

Preservacao gold_visual_before/after.json e gold_visual_verification.json em data/:
todas tabelas de negocio/labels/runs e schema iguais; apenas system_state heartbeat
mudou automaticamente. Commands/configs/security stop e testes legados iguais.
Library45,8candidates,65evidencias,0/45gold reviews permanecem. Nenhum benchmark
novo foi executado no banco real. Nenhum clique TikTok, engagement ou dado externo.
diff--check passou; stat/status revisados, workspace sujo anterior preservado.

Limitacao real: sem thumbnail local; thumbnail remota so abre ao usuario solicitar e
pode estar expirada. Nao coletar novo dado para contornar. Ainda faltam labels humanos.
Tests/test_enrichment.py segue reconstruido, original exato indisponivel; detalhes
historicos preservados abaixo. Nao alegar recuperacao exata nem preencher labels.

---

# Checkpoint atual: Gold Set Review Support

22/10/2026. Ajuste da infraestrutura existente concluido, sem nova arquitetura.
PARAR aqui. Security stop HTTP403 ativo/inalterado; sem navegacao TikTok,
refresh, Companion command, coleta/enrichment/detection ou engagement. Sem commit.

Qualidade / Gold Set:
- Y/N/U = presenca yes/no/unclear, apenas escolha humana de teclado.
- Ctrl+Enter e botao Salvar e avancar usam a mesma rotina; sem duplicar submissao.
- Setas esquerda/direita = anterior/proximo fora de campos de formulario.
- Atalhos apenas em Qualidade sem drawer aberto; letras ignoradas ao digitar.
- Nao preenchem nome/especificidade/confirmacao humana. Nenhum label automatico.
- Drafts/progresso/filtro pending preservados; avancar nao pula video quando item
  revisado sai do filtro pending. Salvar falhou -> continua no mesmo video.
- Candidate/unresolved visiveis em contexto; ate3 comentarios persistidos com
  prioridade textual local, amostra completa expansivel. Sem nova extracao/dados.
- URL do video/evidencias somente texto de referencia no bloco de revisao.
  Thumbnail local/data URI ou URL remota como referencia; nenhum download externo.

Depois de15 reviews humanos: API de salvar calcula/exporta automaticamente
PARTIAL GOLD SET. Recalcula em cada review seguinte, sem duplicar run identico.
Ao concluir45 (todos da Library atual), FINAL GOLD SET / gold-set-v1.
Reporta progresso/yes/no/unclear, TP/FP/FN/TN, precision/recall/F1/naming e topFN/FP.
Unclear e naming pendente continuam excluidos; taxas indefinidas seguem null.
Label commitado ANTES do benchmark; erro de calculo/export preserva review e
mostra mensagem para recalculo local. Nenhuma adaptacao/aprendizado do detector.
Gatilho15 pertence apenas ao relatorio; nenhum threshold operacional foi alterado.

Validacao REAL: ainda0/45 revisados,45pending, yes0/no0/unclear0. Nenhum label ou
benchmark novo foi fabricado. Baseline exportado/run3 anterior permanece; campos
novos evaluation_stage/evaluation_label serao gravados no proximo calculo.
Automatic benchmark a0 retornaNone sem escrita. Library45/candidates8/evidence65,
semantica/resolver/backlog e todas tabelas de negocio iguais ao inicio desta etapa.
Configs, lista de comandos, security stop e testes legados enrichment/backlog iguais.
Somente events/system_state/sqlite_sequence mudaram pelo heartbeat/restart local.
Artefatos: data/review_support_before.json, review_support_after.json e
review_support_verification.json. API gold-set e HTML local validados sem browser.

Testes completos:225 Python passed (4 deprecia??es existentes),96 Node/dashboard
passed. Tasks7ca14a0159cb4e56b80b168038d97345 e237ff4d30a0d41658ab8c107d90ec74c.
Novos casos nos arquivos de testes gold existentes: gatilho14/15/45, final/partial,
export failure sem perda de label, hotkeys/typing guards, avance com pending,
submissao unica e breakdown parcial. Testes com45 labels sinteticos somente em
SQLite temporario; nunca usar esses numeros como resultado real.
Backend restart-backend silencioso: task1dca58791d9540afaf200949cd58cad5 SUCCEEDED.
Sem reload Companion/TikTok. Logs.runtime/logs. diff--check passou; stat/status
revisados; workspace preexistente sujo/untracked, nenhum staging/revert/commit.

Arquivos alterados nesta etapa: app/gold_set.py, app/gold_set_api.py,
app/static/index.html, tests/test_detection_benchmark.py, tests/gold-set-ui.test.cjs,
docs/DETECTION_BENCHMARK.md e este checkpoint. Sem nova tabela ou config.

Pendencia: humano revisar em Qualidade; relatorios automaticos aguardam15 labels,
sem forcar preenchimento ou mudar detector. Validacao real do gatilho requer essas
revisoes humanas; comportamento foi testado em bancos temporarios.
Tests/test_enrichment.py permanece reconstruido com original exato indisponivel;
nao alegar recuperacao exata. Checkpoints anteriores preservados abaixo.

---

# Checkpoint atual: Gold Set + Detection Benchmark v1 (offline)

22/10/2026. Sprint concluido; PARAR. Nenhuma melhoria de detector ou novo modulo.
Security stop HTTP403 continua ativo e inalterado. ZERO navegacao TikTok, refresh,
Companion command, enrichment ou detection run REAL. Sem engagement/staging/commit.

Implementacao local aditiva:
- app/gold_set.py: gold_video_labels, gold_candidate_reviews, gold_review_history e
  detection_benchmark_runs. Labels pending, sem inferir verdade de candidates.
- app/gold_set_api.py: GET /api/gold-set e /{video_id}; POST /{video_id}/review;
  POST /benchmark; GET /benchmark/latest. Nenhum endpoint dispara browser/detector.
- Revisao em Qualidade: 45 videos, caption/creator/URL, candidates como sugestoes,
  comentarios/resumo, evidence, contexto de busca/detail/creator persistido.
  Presenca/specificidade/nome raw/canonical/notas/idioma, name match e forca por
  candidate-video. Confirmacao humana explicita para salvar. Sem auto labels.
- Previous/next, filtro pending e drafts locais preservados, sem autosave/polling.
  PT-BR/ar-EG/RTL. Imagens remotas NAO baixadas: URL de thumbnail preservada e
  ausencia de cache local explicada; preview so se data URI de imagem persistida.
- scripts/detection_benchmark.py exporta data/gold_set_v1.json e
  data/detection_benchmark_v1.json. --record cria pending rows/run; default RO.

Protocolo: gold-set-v1 / detection-benchmark-v1 / gold-benchmark-report-v1.
Resultado PRINCIPAL strict_name_aware: TP exige human yes + name match exact ou
acceptable. Wrong name nao e TP; vira FN estrito (sem candidate aceitavel).
Naming pendente e excluido da matriz estrita. A matriz presence fica SEPARADA,
com FN somente quando nao ha candidate, conforme definicao binaria original.
Presence accuracy nao e naming accuracy. Nomes sao julgados manualmente, nunca
por igualdade automatica de strings. Unclear/pending excluidos; denominador zero=null.
Idiomas escolhidos manualmente; taxas por grupo apenas com >=5 casos elegiveis
(regra de exibicao do benchmark, nao threshold operacional). Ver definicoes completas.

Resultado REAL: 0/45 revisados; 45 pending; yes0/no0/unclear0.
TP0/FP0/FN0/TN0 em zero casos elegiveis (NAO significa acerto/performance).
Precision/recall/F1/presence accuracy/naming accuracy = null/indisponiveis.
FN/FP reasons humanos: nenhum. Coverage8/45=17.78%, apenas cobertura, nao qualidade.
Oito candidates, nove occurrences candidate-video; todas pendentes de auditoria humana:
Soap dispenser(3), dish brush(3), Burger Patty Maker(9), fruit spinner(10),
long-handled floor brush(13), 3 in 1 Window Cleaner(15), Portable Dryer(16),
escova(39 e40). Sem atribuir strong/weak/wrong ou nome humano automaticamente.
Relatorio e doc trazem auditoria explicita dos oito com todos os campos pendentes.

Library permanece45, candidates8, evidence65; 7 observed/1 concept_recurring;
resolver anterior5pares insufficient/0possible; unresolved2pending.
Backlog anterior5complete/38pending/2failed, coverage detail10/comments6/creator17 de45.
Nenhum desses dados operacionais mudou. Nenhuma config, normalizacao, vocabulario,
weight, threshold, candidate, aliases, URL ou detection run alterado.

Runs de construcao do protocolo preservados (1 e2); run ATUAL3 tem politica estrita
explicita, snapshots e fingerprint. Rerun final via funcao e API REAL LOCAL reutiliza
run3/timestamp, sem alterar hashes das quatro tabelas de gold/benchmark. Historico
nao foi apagado. Nova revisao humana exige novo benchmark/export; resultados antigos
continuam snapshots da revisao anterior.

Validacao FINAL: 223 Python passed (4 warnings existentes), 93 Node/dashboard passed.
Tasks: 64b04c150f634c11ba34ea5f74c39b8f e e74237f3ea8547f9bc095aa7824372cc.
Testes novos separados: tests/test_detection_benchmark.py (13 casos) e
 tests/gold-set-ui.test.cjs (4). Label persistence, matrizes, unclear, metrics,
naming, progresso, versoes, idempotencia, drafts/UI/RTL e no detector mutation.
Backend reiniciado silenciosamente SOMENTE por devctl restart-backend, task final
7e04242ab8c643428b5f4b11534285f7 SUCCEEDED. Nenhum reload Companion/TikTok.
Logs em .runtime/logs. API local validada com45pending e contexto real do video39.
git diff --check passou; stat/status revisados. Workspace ja sujo/untracked de
sprints anteriores; sem revert ou commit.

Preservacao: data/benchmark_before.json, benchmark_after.json e
benchmark_verification.json. Todas tabelas antigas de negocio, comandos e configs
iguais. Security stop exato inalterado. Somente events/system_state/sqlite_sequence
mudaram pelo heartbeat/restart e schema_migrations ganhou marcador; quatro tabelas
novas. Nao afirmar identidade fisica do arquivo SQLite. Backup RO antes da migracao:
data/product_hunter.pre_benchmark.db. Testes legados enrichment/backlog com hashes iguais.

Arquivos principais: app/gold_set.py, app/gold_set_api.py,
scripts/detection_benchmark.py, tests/test_detection_benchmark.py,
tests/gold-set-ui.test.cjs, docs/DETECTION_BENCHMARK.md; integracoes em app/db.py,
app/main.py e app/static/index.html. Exports em data/ (nao commitados).

Comandos na .venv existente:
```
.\.venv\Scripts\python.exe scripts/detection_benchmark.py --record
.\.venv\Scripts\python.exe scripts/detection_benchmark.py
.\.venv\Scripts\python.exe scripts/background_runner.py pytest
.\.venv\Scripts\python.exe scripts/background_runner.py node-tests
```
Revisao disponivel na area Qualidade do dashboard local http://127.0.0.1:8000.
Nao abrir TikTok enquanto security stop ativo.

Pendencia REAL: humano revisar os labels/candidate names e classificar FN/FP;
nenhum benchmark de qualidade pode ser concluido antes disso. Nao substituir por
rotulos inventados pelo agente. Texto persistido pode ser insuficiente; usar unclear.
Thumbnails sem cache sao limitacao intencional offline. Sem conclusao sobre desempenho
ou idiomas com amostra pequena. Nao melhorar detector neste sprint.

IMPORTANTE: tests/test_enrichment.py continua RECONSTRUIDO; original exato indisponivel
no Git/historico/backup conhecido. Usuario aceitou preservar cobertura funcional.
Nao alegar recuperacao exata. Checkpoints anteriores preservados integralmente abaixo.

---

# Checkpoint atual: Product Identity Resolver v1 (offline)

22/10/2026. Sprint concluido; PARAR aqui. Nenhum Product final, merge, clustering,
IA/LLM, OCR, visual ou modulo de trend/score foi criado. Sem commit/staging.
HTTP403/security stop ativo e byte-a-byte preservado. ZERO navegacao TikTok,
refresh, Companion command, enrichment ou detection run REAL neste sprint.
Testes usam bancos temporarios e transporte simulado/local.

Implementacao:
- app/product_identity_resolver.py: ocorrencias candidate+video, frases/aliases
  efetivamente observados, captions, creators, URLs e comentarios persistidos.
- product_identity_pairs ampliada ADITIVAMENTE com id, IDs candidate/occurrence/video,
  identity_score /100, semantic_result, reason, evidence_json, resolver_version,
  created_at; updated_at existente. Cinco pares legados preservados integralmente.
- Versao product-identity-resolver-v1; pares novos tem prefixo resolver: e id estavel.
  Semantica/score do PAIR nao altera semantic_status/confidences do candidate.
- Features explicitas com value/weight/contribution/explanation; pesos/penalidades,
  thresholds, vocabulario e limites em config/product_identity.json -> resolver.
- Indice por candidate, tokens especificos, sequencias de frase locais e relacoes.
  Limites 100 ocorrencias/bucket e 1000 pares; truncamento reportado. Sem all-to-all.
- Frases/aliases globais nunca atribuidos a cada video. Numeros/bundles/dimensoes
  preservados; modificadores configurados e estruturas numericas em janela de oito
  tokens perto do head da caption. Brand/model-like sao tokens explicitos, nao campos
  brand/model ou identificacao inferida. Profile/bio/external context nao sao listing.
- URL exata de listing so conta com binding explicito na evidencia; sem abrir link.
- GET /api/product-candidates/resolver-pairs e /resolver-pairs/{id}; POST local
  /api/product-candidates/resolve-identity. Candidate API inclui resolver_pairs e
  possible_identity_matches. API antiga identity-pairs continua so com pares legados.
- Drawer compacto PT-BR/ar-EG/RTL com score /100, decisao, breakdown expansivel,
  capturas textuais/URLs/provenance e aviso permanente Nao mesclado.

Resultado REAL: 45 videos, 8 candidates, 65 evidencias, nove ocorrencias de candidates.
5 pares avaliados: 0 different, 5 insufficient, 0 possible_same_product. Sem truncamento.
Top 5: escova (39) vs escova (40) = 10/100; Window Cleaner(15) vs Portable Dryer(16),
Soap dispenser(3) vs dish brush(3), Burger Patty Maker(9) vs Window Cleaner(15),
Burger Patty Maker(9) vs Portable Dryer(16) = todos 0/100. Nenhum possible match.

Escova: normalized phrase/alias local escova em ambos; head generico nao soma.
Compartilha modificador contextual eletrica (+10); B tem 9 em 1/extensivel,
A nao. Numero ausente nao e conflito. Zero supporting comments/listing. Insufficient.
Creators @isadoravalebr / @vitrineglei; captions e URLs completos no doc abaixo.
Candidate continua concept_recurring; deteccao42/recorrencia60/identidade-legada0,
legacy corroborated64 preservado. Score do PAIR10 nao substitui essas dimensoes.
Vacuum cleaner vs Mini Vacuum Cleaner = 30/100 insufficient, mesmo video;
comparacao diagnostica apenas. Duas unresolved continuam pending, sem promocao.

Preservacao verificada contra backup RO e snapshots: todas tabelas de negocio,
observacoes, aliases, evidencias, URLs, candidates, runs, semantica/historico anteriores,
backlog, bridge_commands e dev_commands iguais. Cinco pares anteriores preservados
em suas colunas originais; cinco novos resolver pairs adicionados. Tabelas operacionais
system_state/events/sqlite_sequence mudaram pelo heartbeat/restart; migration marker
adicionado. Nao afirmar que o arquivo SQLite ficou fisicamente identico.
Backlog permanece 5 completos/38 pendentes/2 failed; detail10/comments6/creator17 de45.
Testes test_enrichment.py e test_backlog.py byte-a-byte iguais ao inicio deste sprint.
Configs antigas iguais, salvo adicao da secao resolver em product_identity.json.

Validacao FINAL: 210 Python passed, quatro warnings de depreciacao existentes;
89 Node/dashboard passed. Quinze testes novos Python separados em
 tests/test_identity_resolver.py; dois DOM em tests/identity-resolver-ui.test.cjs.
Tasks finais: e0efea5a857f4d328ce0a64b31d5b558 e 2a1dcc3e90c043eda21f68e4ccb20308.
Backend reiniciado somente via devctl restart-backend, silencioso, task final
 e1f98522f8ac4716a1d852d122ad384b SUCCEEDED. Nenhum reload de Companion/TikTok.
API LOCAL verificada com cinco pairs e oito candidates. Resolver rerun real idempotente:
mesmo relatorio e hash integral da tabela, sem alterar created_at/updated_at.
git diff --check passou; git diff --stat e git status revisados. Workspace ja sujo
com muitos arquivos untracked anteriores; nenhum revert, staging ou commit.

Arquivos principais novos: app/product_identity_resolver.py,
scripts/resolve_product_identity.py, tests/test_identity_resolver.py,
tests/identity-resolver-ui.test.cjs, docs/PRODUCT_IDENTITY_RESOLVER.md.
Integracoes: app/db.py, app/candidate_semantics.py (INSERT com colunas explicitas,
separacao dos pares legados), app/product_detection.py, app/product_candidate_api.py,
app/static/index.html, config/product_identity.json e docs/PRODUCT_IDENTITY.md.

Relatorio completo: docs/PRODUCT_IDENTITY_RESOLVER.md.
Artefatos: data/product_identity_resolver_report.json, resolver_before.json,
resolver_after.json, resolver_verification.json; backup data/product_hunter.pre_resolver.db.
Logs em .runtime/logs. Escalas: resolver identity_score/concept_similarity_score /100;
legacy product_identity_score /1. Filtrar resolver_version antes de ler pares diretamente.
Pares legados tem novas colunas null; nao atribuir nova decisao retroativa.

Comandos locais (na .venv existente):
```
.\.venv\Scripts\python.exe scripts/resolve_product_identity.py
.\.venv\Scripts\python.exe scripts/resolve_product_identity.py --apply
.\.venv\Scripts\python.exe scripts/background_runner.py pytest
.\.venv\Scripts\python.exe scripts/background_runner.py node-tests
```
Default RO; --apply so migra/resolve SQLite, sem detection ou navegador.

Limites: score heuristico nao probabilistico; different indica conflito heuristico,
nao certeza fisica. Vocabululario/case/adjacencia de caption podem ser ambiguos;
URLs nao verificadas externamente. Nenhum score confirma mesmo produto fisico.
Nao existe pendencia que autorize navegar com o security stop ativo.

IMPORTANTE: tests/test_enrichment.py continua RECONSTRUIDO, original exato
indisponivel no Git/historico/backup conhecido. Usuario aceitou preservar essa
reconstrucao funcional. Nao alegar recuperacao exata. Checkpoints anteriores abaixo.

---

# Checkpoint atual: semantica de recorrencia e identidade (offline)

22/10/2026. Sprint concluido. Parar aqui: nao iniciar clustering ou outro modulo.
HTTP 403/security stop continua ativo e inalterado; nenhuma navegacao, refresh,
comando TikTok, enrichment ou detection run real neste sprint. Sem engagement/commit.

Implementacao aditiva `product-identity-foundation-v1`:
- `candidate_semantics`, `candidate_semantic_history`, `product_identity_pairs`,
  `product_identity_evidence`; scores/status/runs/evidence/aliases/URLs legados preservados.
- `semantic_status` separa observed, concept_recurring, possible_same_product e
  product_matched (reservado; nunca automatico).
- detection_confidence, recurrence_confidence, identity_confidence separados;
  specificity e product_signature preservam raw, numeros e modificadores.
- API list/detail aditiva e GET /api/product-candidates/identity-pairs.
- Dashboard compacto/lista/drawer PT-BR + ar-EG/RTL: conceito recorrente, identidade
  nao confirmada, especificidade, tres dimensoes, pares e historico auditavel.
- Pesos/thresholds antigos NAO alterados; nova config product_identity.json.

Dados reais: 45 videos, 8 candidates, 65 evidencias. Sete observed, escova
concept_recurring; zero possible_same_product e zero product_matched. Escova:
deteccao 42%, recorrencia 60%, especificidade 5/100, identidade 0%; legado
corroborated/64% intacto. Dois videos/creators, seis captions historicas, zero
supporting comments, grupos video:39 e video:40. Fixture real isolada em
tests/fixtures/product-identity-escova.json. Captions, creators e URLs completos
no relatorio docs/PRODUCT_IDENTITY.md. Outros candidates: deteccao 42%,
recorrencia/identidade 0%, especificidades 30/30/55/30/55/45/35.
Vacuum cleaner (30/100) e Mini Vacuum Cleaner (50/100) continuam pending.
Library/backlog: 5 completos, 38 pendentes, 2 failed; cobertura anterior preservada:
detail 10/45, comments 6/45, creator 17/45. Nenhum dado novo coletado.

Validacao final: 195 Python passed (4 warnings existentes), 87 Node/dashboard
passed. Task IDs: bc0ff36477da4a4caf7cb230d4a74189 e
0a52e7e86c6c4d65823c3432fb000976. Testes novos isolados em
tests/test_product_identity_semantics.py (14 casos). Teste UI adicionado e assert
do badge legado atualizado para semantic_status. Testes enrichment/backlog antigos
continuam byte-a-byte iguais ao inicio deste sprint. git diff --check passou;
git diff --stat e git status revisados. Workspace ja continha muitas mudancas
anteriores e arquivos untracked; nao staged/commit/revert.

Backend reiniciado silenciosamente via devctl restart-backend (task
9eb7af1546784253a3df2da9aae359bd, SUCCEEDED). Nao houve reload de Companion/TikTok
ou abertura de navegador. Logs em .runtime/logs. API LOCAL validada com oito
candidates; rerun semantico no banco real manteve hashes de todas quatro tabelas.
Dados legados de negocio, lista integral de comandos, security stop e configs
anteriores permanecem iguais. Tabelas operacionais events/system_state e sequencia
mudaram por heartbeat/ciclo de vida do backend; schema_migrations ganhou marcador.
Nao afirmar que o arquivo SQLite ficou fisicamente identico.

Arquivos principais deste sprint:
app/candidate_semantics.py, config/product_identity.json, app/db.py,
app/product_detection.py, app/product_candidate_api.py, app/static/index.html,
scripts/product_semantics_report.py, tests/test_product_identity_semantics.py,
tests/fixtures/product-identity-escova.json, tests/dashboard-ui.test.cjs,
docs/PRODUCT_IDENTITY.md e avisos nos docs PRODUCT_CANDIDATES/PRODUCT_CORROBORATION.

Artefatos locais: data/product_hunter.pre_semantics.db (backup),
data/semantics_before.json, semantics_after.json, semantics_verification.json,
semantics_live_validation.json e product_semantics_report.json.

Comandos locais uteis (na .venv existente):
```
.\.venv\Scripts\python.exe scripts/product_semantics_report.py
.\.venv\Scripts\python.exe scripts/product_semantics_report.py --apply
.\.venv\Scripts\python.exe scripts/background_runner.py pytest
.\.venv\Scripts\python.exe scripts/background_runner.py node-tests
```
Relatorio default e SQLite RO; --apply so recalcula tabelas semanticas/marcador,
sem detection/enrichment. Inspecionar JSON/log da tarefa para confirmar sucesso.

Limitacoes reais: heuristicas lexicais limitadas, scores nao calibrados; identidade
zero significa insuficiencia. Pares entre candidates relacionados nao promovem
status automaticamente; falta validar ocorrencias. Nao ha propagacao transitiva.
Sem brand/model/resolver/visual/OCR/LLM/final Product. Security stop exige manter
operacoes TikTok paradas; nenhum bypass ou tentativa de recuperacao.

IMPORTANTE: tests/test_enrichment.py continua RECONSTRUIDO; original exato
indisponivel no Git HEAD/historico/backup conhecido. Usuario aceitou preservar
reconstrucao e cobertura funcional. Nao alegar restauracao exata. Detalhes e
checkpoint anterior integral abaixo.

---

# Babi — checkpoint atual: recuperação de testes e auditoria offline

22/10/2026. Nenhum novo sprint de produto foi iniciado. Nenhuma navegação TikTok,
refresh, comando, lote, detection run, aprovação ou alteração de threshold nesta etapa.

## Limitação da recuperação exata — confirmada com o usuário

`tests/test_enrichment.py` **não existe no Git HEAD**
`fd727e165bffde0987a617383fb4e7d107cd21d4`. `git show HEAD:tests/test_enrichment.py`
retorna fatal; o caminho não tem histórico nas referências locais. Nenhuma versão
recuperável foi encontrada em outros objetos. O usuário confirmou não conhecer
commit/branch/backup exato e instruiu preservar o estado funcional.

O arquivo atual é **reconstruído**, não o original recuperado. Não houve nova
reconstrução nem alegação de recuperação exata nesta etapa. Seus 36 casos e a
fixture result() foram preservados sem edição. Novos testes continuam separados em
`tests/test_backlog.py`. Hashes dos dois arquivos antes/depois iguais. Nenhuma
cobertura que estava passando foi apagada.

Todos os nomes de testes rastreados no HEAD continuam presentes nos arquivos atuais;
isso não garante equivalência dos corpos alterados em sprints anteriores nem do
original não versionado indisponível. Não declarar o incidente como recuperação
histórica exata concluída. O usuário aceitou explicitamente essa limitação.

## Validação local final

- **181 Python passed**, quatro depreciações existentes.
- **86 Node/dashboard passed**.
- Tarefas finais: Python `6b58c48d998f4840919526c2037eaa38`,
  Node `69841c5ea934412eb2a90b9514a8f0b3`.
- Apenas SQLite RO (`mode=ro`, `query_only=ON`); nenhum app/db, migração ou API real
  foi usada pela auditoria. Testes usam bancos temporários.
- Todas as tabelas de negócio e a lista integral de comandos ficaram iguais.
  Security stop e configurações também. Só `system_state.tiktok_bridge` foi
  atualizado pelo heartbeat automático do processo que já estava em execução.
  Não afirmar que o arquivo SQLite ativo ficou fisicamente idêntico.
- Sem alteração de fórmula/score/status/vocabulário/broad flags. Sem commit.

## Diagnóstico offline e pendências

Relatório completo: [OFFLINE_AUDIT.md](OFFLINE_AUDIT.md).
Artefatos: `data/offline_candidate_audit.json`, snapshots before/after e
`data/offline_recovery_verification.json`. Script local reutilizável:
`scripts/offline_candidate_audit.py`; não navega nem escreve no banco.

8 candidates: 7 observed/42%, escova corroborated/64%; 65 evidências = 53 captions
+ 12 profile links. Zero problemas nos checks estruturais de provenance e zero
dedup_keys duplicadas. Há 44 repetições históricas adicionais de caption dentro
dos candidates; não são fontes independentes.

Escova permanece broad_concept=true, 2 vídeos/2 creators, 0 supporting comments,
strong_explicit_phrase=false. Regra A não exige especificidade forte nem comentários;
aceita dois vídeos/dois usernames e acrescenta 22 pontos. Risco de supercorroborar
um conceito lexical se o resultado for interpretado como mesmo produto físico.
**Diagnóstico somente; nenhuma regra alterada.**

Portable Dryer pode continuar amplo apesar de broad_concept=false. Soap dispenser
e dish brush vêm da mesma caption de item combinado, não provam dois produtos físicos.
Vacuum cleaner e Mini Vacuum Cleaner continuam pending: um vídeo, dois autores/textos
distintos; um comentário foi observado novamente em outro sample. Não aprovar/mesclar.

Library/backlog inalterados: 45 vídeos; 5 completos, 38 pendentes, 2 com falhas.
Cobertura válida detail 10/45, comments 6/45, creator 17/45. Nenhum dado novo coletado.

**HTTP 403 continua ativo. Não navegar nem tentar recuperação automática.**
Somente tarefas locais/offline enquanto durar o bloqueio. Nenhuma nova conta,
janela, user-agent, headers, proxy, bypass ou refresh/retry para recuperar TikTok.

---

## Histórico preservado: sprint anterior de backlog

# Babi — checkpoint: Backlog Enrichment + Evidence Expansion

22/10/2026. Sprint encerrado; sem commit. Não iniciar outro módulo/sprint.
Workspace `C:\product-hunter-tiktok-v0.1.4`, ambiente `.venv` existente.
O workspace já contém muito trabalho não commitado de sprints anteriores.

## PARADA REAL DE SEGURANÇA — NÃO CONTINUAR NAVEGANDO

HTTP **403** observado em **2026-10-22T12:25:59.604Z**, no documento:
https://www.tiktok.com/@vitrineglei/video/7673992589036506388

Stop persistente em chrome.storage.local/securityStop e
system_state/browser_security_stop. Nenhum bypass, refresh de TikTok, retry de
navegação, troca de identidade ou limpeza do latch foi feito. Depois do 403 houve
somente testes, auditoria, documentação e reinícios locais do backend, sem recarga
de Companion/TikTok. O bloqueio permanece. Revisão humana é necessária antes de
qualquer recuperação; não apagar o latch apenas para completar o backlog.

Chrome permaneceu aberto, processo principal 71320, uma aba TikTok 244955580,
janela 244955513. Companion 0.1.5, build d0d95f70d86508ef. Nenhum novo Chrome/aba.
Backend supervisionado saudável. Não há comandos de coleta ou lotes em execução.

## Implementação entregue

- Estados persistentes por vídeo/etapa em enrichment_stages:
  pending, running, complete, failed, not_applicable; IDs de comando/observação,
  motivo e timestamps. Cinco etapas: detail, comments, creator, product_detection,
  corroboration. GET reconcilia observações válidas e persiste transições.
- enrichment_batches registra seleção de até 5, progresso, stop flag e checkpoint.
  Índice único impede dois lotes simultâneos. Worker local em thread, sem CMD.
  Os leitores existentes continuam na Companion, mesma aba e pacing existente.
- Seleção lexicográfica transparente: origem discovery, caption útil, hipótese ou
  unresolved, creator desconhecido; desempate por first_seen recente e ID.
- Verificação antes de cada etapa: não reabrir detail/sample válido; perfil recente
  reutilizado por video_creators (janela de 168h). Comments target continua 30.
- Falha terminal confirmada é isolada; outros vídeos continuam quando seguro.
  Comments sem detail válido ficam not_applicable. Resultado de transporte incerto
  interrompe o lote, evitando replay de ação ainda possivelmente ativa.
- Stop termina o vídeo atual antes de parar. Backend reiniciado marca lote
  interrupted e reconcilia dados; retomada exige novo lote explícito. DEV CONTROL
  inclui lote ativo no drain. Não reiniciar/abortar lote ativo por conveniência.
- Product detection escopado ao vídeo após as etapas disponíveis; detector existente
  recalcula corroboration/relationships atomicamente. Nenhum peso/threshold mudou.
- Diagnóstico broad_concept aditivo, sem mudar score/status ou fazer merge.
- Bloco compacto em Coleta: contagens, próxima execução, stop, progresso e lista
  recolhível de etapas por vídeo. PT-BR/ar-EG/RTL. Sem página nova/redesign.
- Segurança aparece na UI e desabilita o botão de novo lote; API também recusa.

## Execução real

Snapshot anterior: data/backlog_before.json; backup data/product_hunter.pre_backlog.db.
Relatório consolidado: **data/backlog_validation.json**.

O backlog completo tinha 40 pendentes e 5 completos, incluindo 26 novos do sprint
anterior e pendências antigas. Contagens de cobertura são por vídeos distintos,
não por quantidade de observações históricas.

Lote #1 falhou localmente antes de qualquer navegação: faltou type obrigatório na
construção do modelo de comando. Erro corrigido e coberto por teste do contrato
real dos três modelos. Registro preservado; não foi ocultado nem contado como coleta.

Lote #2 selecionou vídeos Library **39, 40, 45, 43, 44**. Foi interrompido no segundo:

- #95 VIDEO DETAIL do vídeo 39: SUCCEEDED, observação nova válida.
- #96 COMMENTS SAMPLE do vídeo 39: SUCCEEDED, 30 comentários, target_reached.
- #97 CREATOR PROFILE do vídeo 39: FAILED, header/username não prontos; nenhuma
  observação de perfil inventada. Hidden não foi usado como gate; o DOM era vazio.
- Detection run #20 incorporou uma evidência, sem candidate novo.
- #98 VIDEO DETAIL do vídeo 40: FAILED por HTTP 403; parada de toda navegação.
- Os outros três selecionados não foram iniciados. Nenhum próximo lote foi aberto.

Checkpoint #2: videos_processed=2, detail_complete=1, comments_complete=1,
creator_complete=0, failed=2, new_candidates=0, updated_candidates=1,
new_evidence=1, new_unresolved_phrases=0.

## Resultado final real

- Library **45 vídeos**, sem novas buscas/discovery neste sprint.
- Vídeos que receberam dados novos: **1 parcial**; **0 novos completos**.
- Estado global: **5 completos, 38 pendentes, 2 com falhas, 0 processando**.
- Ainda precisam de conclusão: **40**; os 26 novos anteriores continuam sem
  conclusão integral (um recebeu detail/comments).
- Cobertura válida por vídeo: detail **10/45**, comments **6/45**, creator **17/45**.
  Creator inclui reuso de perfil recente do mesmo creator.
- Histórico: 167 search observations, 21 detail observations, 12 samples,
  232 comment observations, 22 profile observations.
- Intelligence: **8 candidates**, 7 observed, 1 corroborated, 1 cross-video,
  1 cross-creator, **65 evidências**, 2 unresolved phrases (vacuum cleaner /
  Mini Vacuum Cleaner). Vocabulário product-vocabulary-v1, nenhuma aprovação.
- Reruns locais escopados ao vídeo 39 (#21/#22) criaram 0 candidates/evidências;
  aliases/URLs/evidence counts permaneceram iguais. Não navegaram no TikTok.
- integrity_check=ok; foreign_key_check vazio. Todas as observações históricas
  auditadas preservadas sem alteração. Nenhuma URL foi removida.

## Escova

Revisão detalhada: [ESCOVA_REVIEW.md](ESCOVA_REVIEW.md).
Snapshots: data/escova_before_backlog.json e escova_after_backlog.json.

- Vídeo 39: @isadoravalebr, 7657730138993446151; caption de escova elétrica
  giratória para rejunte/cantos.
- Vídeo 40: @vitrineglei, 7673992589036506388; caption de escova elétrica 9 em 1.
- Raw phrase, normalized phrase, signature e alias: **escova**.
- Grupos independentes video:39 e video:40; 2 creators. Cinco evidências de caption
  iniciais eram duas origens; detail acrescentou uma evidência no mesmo grupo 39.
- Zero supporting comments de identidade, inclusive após a amostra nova.
- Regra A existente: 0,42 base + 0,12 segundo vídeo + 0,10 segundo creator = **0,64**.
  Confidence e status inalterados; **broad_concept=true** diagnóstico.
- Os textos sustentam categoria comum de escova elétrica de limpeza. Não provam
  mesmo modelo, marca, SKU ou produto físico. Nenhum merge/Resolver foi feito.

## Testes e incidente de desenvolvimento

**181 Python passed**, 4 avisos de depreciação existentes; **86 Node/dashboard passed**.
Inclui backlog selection, limite, skip/reuse, failure isolation, checkpoint,
stop/resume, idempotência, segurança, contratos reais, UI PT/RTL e regressões.

Ao criar testes houve colisão com tests/test_enrichment.py, que era não rastreado.
O corpo original foi sobrescrito e não foi recuperado byte a byte. Sua interface
result() e 36 casos de regressão foram reconstruídos usando os contratos, fixtures
e os nomes originais preservados no cache do pytest. A nova cobertura inclui
normalização, precedência, métricas, snapshots, migração, counters, dedup e history.
Novos testes estão separados em **tests/test_backlog.py**. A suíte completa passa;
esta reconstrução deve ser revisada como parte do diff, sem presumir identidade do
arquivo anterior. Nenhum dado da Library foi afetado pelo incidente.

Logs finais e IDs de testes estão em data/backlog_validation.json. git diff --check,
git diff --stat e git status conferidos; diff cumulativo inclui sprints anteriores.
Nenhum staging/commit. Nenhum engajamento TikTok.

## Arquivos principais

Novos: app/enrichment.py, app/enrichment_api.py, config/enrichment.json,
tests/test_backlog.py, docs/ENRICHMENT_BACKLOG.md, docs/ESCOVA_REVIEW.md.
Integrações: app/db.py, app/main.py, app/dev_control.py, app/product_detection.py
(somente serialização broad_concept), app/static/index.html, README e dashboard tests.

## Comandos locais seguros

```powershell
.\.venv\Scripts\python.exe scripts/background_runner.py devctl status
.\.venv\Scripts\python.exe scripts/background_runner.py pytest
.\.venv\Scripts\python.exe scripts/background_runner.py node-tests
.\.venv\Scripts\pythonw.exe scripts/devctl.pyw status
```

Conferir task-ID.json e task-ID.log em .runtime/logs; submissão não é sucesso.
GET /api/enrichment mostra estados/observações/checkpoints. POST /api/enrichment/batches
inicia até 5; retry_failed:true é explícito; /batches/{id}/stop termina o vídeo atual.
**Não usar os POSTs de coleta enquanto o bloqueio de segurança persistir.**

Não implementar Clustering, LLM, OCR/visual, marca/preço, Trend Engine, Gold Score
ou Brazil Gap. Prioridade futura depende de revisão humana do 403, sem bypass.
Checkpoint anterior arquivado em data/next_session_pre_backlog.md.
