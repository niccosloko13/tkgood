# BABI — Visual Product Identification v1

Pipeline assistida implementada; nenhum nome foi inventado. O piloto real encontrou somente referências remotas TikTok CDN, sem imagens locais acessíveis. Nenhuma imagem remota foi requisitada, nenhum provider remoto foi chamado e o security stop continua intacto. Sem commit.

## HIGH QUEUE

| Video ID | Caption | Fonte | Disponibilidade | Motivo |
|---|---|---|---|---|
| 2 | Easy to clean kitchen😏 #gadgets | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 4 | 🔗Link in bio. Amazon Home Finds | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 5 | — | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 6 | Você esqueceu de desconectar? | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 11 | — | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 12 | Easy to dry clothes in house😏 #gadgets | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 14 | 🔗In Bio! Kitchen Gadgeg I Use Daily🥚🤍 | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 29 | No more stirring! 🌪️☕ | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 30 | Easy to store eggs😏 | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 33 | Easy to store peppers😏 | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 34 | Prep like a pro, without doing the work 🔪🥑 Say goodbye to chopping by hand. | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 35 | Easy to squeeze out toothpaste😏 | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 38 | Watching this thing slice is way too satisfying 🥕⚡ Just feed it in and the slices keep coming. | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |
| 43 | Interruptor de um clique! Muito fácil de usar, até quem não tem prática na cozinha consegue. Triture temperos e grãos em segundos. Design moderno e tampa transparente para você ver o resultado! | remote_thumbnail | visual_unavailable | blocked_by_security_stop_tiktok_cdn |

Os 14 contextos completos em high-review-items.json contêm thumbnail_url persistida (referência apenas), hashtags, comentários relevantes, candidates, unresolved, categoria/subcategoria/family e motivos da prioridade. Nenhum MEDIUM foi expandido. Seleção inicial congelada em visual_pilots/visual_pilot_items.

## VISUAL AVAILABILITY

| Métrica | Resultado |
|---|---|
| visual_items_attempted | 14 |
| visual_available | 0 |
| visual_unavailable | 14 |
| provider_calls | 0 |

Attempted significa verificação local da fonte, não análise de imagem. Fontes em p16/p19-common-sign.tiktokcdn.com são blocked_by_security_stop_tiktok_cdn. Não foram testadas disponibilidade HTTP, expiração ou conteúdo dessas imagens. Nenhum frame/cache de navegador foi procurado e nenhuma imagem alternativa foi fabricada. O retorno da internet não revoga o bloqueio TikTok.

## PRODUCT SUGGESTIONS

| Métrica | Resultado |
|---|---|
| visual_suggestions | 0 |
| human_accepted | 0 |
| human_rejected | 0 |

Sem imagem acessível, zero propostas V1 foram inseridas em VisualProductEvidence; nomes do Gold Set, captions e queries não foram usados para fingir saída visual. O fluxo assistido está disponível para imagens locais reais associadas pelo operador. Novas propostas começam em suggested; accepted/rejected/unclear exigem ação humana e guardam histórico. Aceitação não confirma entidade nem grava candidates/labels.

## GOLD SET COMPARISON

| Video ID | Nome humano preservado | Nomes visuais | Match | Helpful | Wrong | Visual unavailable |
|---|---|---|---|---|---|---|
| 1 | vacuum cleaner |  | — | — | — | True |
| 2 | mini mop |  | — | — | — | True |
| 3 | Soap dispenser and dish brush |  | — | — | — | True |
| 4 | floor cleaning brush |  | — | — | — | True |
| 5 | electrical outlet expander |  | — | — | — | True |
| 6 | Intelligent Full Power Automatic Separator  |  | — | — | — | True |
| 7 |  |  | — | — | — | True |
| 8 | Oil Spray |  | — | — | — | True |
| 9 | Burger Patty Maker |  | — | — | — | True |
| 10 | Fruit Cleaner Spinner  |  | — | — | — | True |
| 11 | mini seladora térmica portátil |  | — | — | — | True |
| 12 | varal retrátil de corda dupla |  | — | — | — | True |
| 13 | floor brush |  | — | — | — | True |
| 14 | Kitchen Gadgeg |  | — | — | — | True |
| 15 | Window Cleaner |  | — | — | — | True |

Comparação somente leitura dos 15 reviews existentes. Nenhum provider foi executado fora dos HIGH. Checar a referência de imagem dos demais reviews para comparar disponibilidade não expande o piloto. Nome igual após NFKC/casefold é comparação literal, não identidade física; nomes diferentes não são automaticamente wrong. Helpfulness/wrong exigem avaliação humana separada, sem alterar Gold.

## FALSE NEGATIVE IMPROVEMENT

visual_helpful_on_FN: 0 observados; visual_match_on_gold_set: 0 em 0 comparações avaliáveis. Taxa: None. Melhoria de recall **não medida**; zero observações não demonstra que visão seja inútil. Os 9 FN e o recall humano/detector anteriores não foram recalculados nem reclassificados.

## PROVIDER PERFORMANCE

| Provider | Integração | Execução real |
|---|---|---|
| vision_model | assistida/manual; sem API remota configurada | 0 chamadas remotas |
| web_image_search | assistida/manual; sem API remota configurada | 0 chamadas remotas |
| google_lens_assisted | assistida/manual; sem API remota configurada | 0 chamadas remotas |

Estados do piloto: {&quot;not_called_image_unavailable&quot;: 14}. Não é possível medir precisão/recall ou comparar providers sem imagens/resultados. Não foi criado workaround de Lens. A interface aceita saída atribuída com source_type, provider_version, URL, observed_at, reason, confidence declarada e hash da imagem.

## MULTI-SOURCE / CONFIDENCE / UI

Hipótese separa texto, comentários, visual e web listings por IDs de evidência. Aliases são sugestões deduplicadas, não sinônimos confirmados. Confidence: 0,25 visual; +0,10 caption literal; +0,10 comments; +0,25 para duas fontes/listings compatíveis em sites/grupos independentes com revisão explícita. Cap0,70; genericidade/contradição cap0,20. Resultado único nunca excede0,45. Não são probabilidades.

Novo painel VISUAL IDENTIFICATION dentro do review e fila HIGH em Vídeos. ACEITAR/REJEITAR/INCERTO alteram somente a revisão visual. Imagens são servidas apenas pelo endpoint local validado; referências CDN não viram src. Após proposta, há link de pesquisa web acionado pelo humano e formulário title/url/source/observed_at/possible_match/match_reason, compatibilidade/contradição/independência. Referências web são evidência de identidade, não SupplierListingEvidence. Nenhuma busca web ocorreu sem hipótese visual.

## UNRESOLVED CASES

Todos os 14 HIGH continuam sem identificação visual nesta execução. É necessária uma imagem real persistida localmente; não obter novas imagens do TikTok durante o bloqueio. A fila e os motivos estão preservados. Adapters assistidos não substituem uma integração remota oficial e não prometem inferência automatizada. Site buckets não provam independência societária; a revisão humana é obrigatória e cópias entre sites ainda podem enganar. A comparação literal não mede sinônimos nem modelo/SKU.

## PRESERVATION

{&quot;changed_original_tables&quot;: [&quot;events&quot;, &quot;sqlite_sequence&quot;, &quot;system_state&quot;], &quot;changed_existing_files&quot;: [&quot;app\\db.py&quot;, &quot;app\\main.py&quot;, &quot;app\\static\\index.html&quot;, &quot;docs\\NEXT_SESSION.md&quot;], &quot;integrity_check&quot;: &quot;ok&quot;, &quot;foreign_key_check&quot;: [], &quot;extension_unchanged&quot;: true, &quot;browser_security_stop_unchanged&quot;: true, &quot;browser_security_history_unchanged&quot;: true, &quot;browser_security_clearance_unchanged&quot;: true}

Schema novo é aditivo: seis tabelas de assets/reviews/web/piloto/comparação e colunas em visual_product_evidence. Gold Set, benchmark, candidates, evidence anteriores, detector, classifier, taxonomy, resolver e SupplierListingEvidence não foram alterados. Legado visual permanece com status original e não foi convertido em confirmação. Backup: checkpoint.db; baseline:before.json.

## TEST RESULTS

| Suite | Passed | Task |
|---|---|---|
| python | 288 | b15beded9bad4c4791f3333e12d8d62f |
| node_dashboard | 116 | ceda63ed5f5841f1a13c20773b89bc7c |

Logs em .runtime/logs/task-ID.json/.log. Testes sintéticos usam imagens em bancos/pastas temporários, não imagens reais do piloto.

## FILES CHANGED

app/visual_identification.py, app/visual_identification_api.py, app/db.py, app/main.py, app/static/visual-identification.js, app/static/index.html; tests/test_visual_identification.py, tests/visual-identification.test.cjs; scripts/visual_identification_report.py; docs/VISUAL_IDENTIFICATION.md e docs/NEXT_SESSION.md. Artefatos JSON, report e checkpoint nesta pasta. Workspace anterior preservado; sem staging/commit.

## NEXT RECOMMENDED SPRINT

Associar imagens locais reais e revisar os mesmos HIGH pelo fluxo assistido; coletar propostas e avaliações separadas antes de medir benefício nos FN. Só então avaliar integração oficial de provider com credenciais/limites/provenance adequados. Não expandir para MEDIUM, não reabrir TikTok, não limpar stop e não iniciar Supplier Discovery automaticamente.
