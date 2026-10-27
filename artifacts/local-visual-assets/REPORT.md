# BABI — Local Visual Assets + Assisted Product Identification

Implementado sobre VisualProductEvidence v1, sem reconstruir a entidade. Snapshot: 2026-10-23T19:13:00.137603+00:00.

## RESULTADOS REAIS

| Métrica | Resultado |
|---|---|
| assets_uploaded | 0 |
| assets_total | 0 |
| HIGH_resolved | 0 |
| HIGH_remaining | 14 |
| Gold_FN_tested | 0 |
| visual_attempted | 0 |
| visual_helpful | 0 |
| visual_match | 0 |
| visual_wrong | 0 |
| still_unclear | 7 |
| helpfulness_assessed | 0 |

HIGH resolved significa imagem local disponível, não identidade confirmada. still_unclear considera somente os 7 itens HIGH com review humano existente. Zeros de helpful/wrong não são estimativas de qualidade: não houve julgamento avaliável enquanto faltam imagens/resultados reais.

**Nenhuma imagem real foi fornecida nesta execução.** O usuário confirmou que vai adicioná-las pelo review. Nenhum arquivo de teste foi inserido na biblioteca real, nenhum asset/produto foi fabricado e nenhuma URL CDN foi baixada para preencher essa lacuna. O fluxo está disponível para uso, mas a identificação real dos FN aguarda esses uploads e o resultado assistido.

## LOCAL ASSET INGEST

Upload binário, seleção de arquivo e drag & drop por video_id. PNG/JPG/JPEG/WebP com verificação completa de decoder/MIME, integridade e dimensões por Pillow12.3.0, no ambiente .venv existente. Limites:10MiB,8192px/lado,20M pixels; imagens animadas/corrompidas rejeitadas. Content-Length e chunks são limitados. MIME/extensão devem corresponder ao conteúdo. SHA256 usa os bytes originais, sem resize ou transcode.

Armazenamento:data/visual_assets/{video_id}/{sha256}.{ext}. Asset registra video_id,asset_id,source_type,local_path,sha256,width,height,created_at. Dedup por video_id+sha256; upload repetido não cria outro asset. O mesmo conteúdo em outro vídeo é associação explícita distinta. Filename humano não vira path de destino. Upload seleciona asset local sem alterar thumbnail_url, que continua referência remota.

## GOLD SET PILOT

| Ordem | Video ID | Gold status existente | Imagem |
|---|---|---|---|
| 1 | 4 | fn | visual_unavailable |
| 2 | 5 | fn | visual_unavailable |
| 3 | 6 | fn | visual_unavailable |
| 4 | 11 | fn | visual_unavailable |
| 5 | 12 | fn | visual_unavailable |
| 6 | 14 | fn | visual_unavailable |
| 7 | 2 | unclear | visual_unavailable |

FN primeiro:4,5,6,11,12,14;depois item2 incerto. Nenhum MEDIUM é expandido. Upload é permitido em outros HIGH, mas o início assistido fica restrito à interseção HIGH/Gold. IDENTIFICAR PRODUTO prepara pacote local(video_id,imagem/hash,caption,comments,category,candidate,unresolved), sem chamar provider. Comparação e helpfulness são registros visuais separados; Gold labels e benchmark não mudam.

## ASSISTED LENS / WEB CONFIRMATION

O review oferece Adicionar imagem, preview local, IDENTIFICAR PRODUTO, download local e link manual para Lens. O operador escolhe o arquivo no fluxo normal do Google e registra possible_product_name,result_url,source,listing_title,observed_at,notes. A Babi não envia imagem ao Google nem automatiza navegador/Lens. Saída sempre google_lens_assisted/suggested; referência inicial não ganha match/compatibilidade/independência automaticamente.

Referência de operação assistida:[Google Lens](https://lens.google/), página oficial consultada; isso não é integração de API ou scraping. Após nome possível, formulário web guarda title,url,domain derivado,possible_match,match_reason,independence_reviewed e snapshots datados, sem scraping/preço/supplier lookup. TEXT,VISUAL,WEB CONFIRMATION e FINAL HYPOTHESIS permanecem separados no review.

## CANONICAL / REVIEW HISTORY

Canonical name suggestion escolhe apenas nomes observados no resultado visual, aliases propostos ou títulos curtos marcados como possíveis matches/compatíveis. Prefere suporte literal em caption, depois comments, depois nome visual original. Títulos podem aparecer como aliases sugeridos com IDs de fonte; nenhuma equivalência semântica é confirmada nem nome híbrido inventado. Nenhuma Product Entity é criada.

Imagem nova tem novo hash/draft e requer nova preparação. Proposta/revisão da imagem anterior permanece histórica e não é aplicada à atual. Upload que termine atrasado não substitui outro review selecionado. Aceitar/rejeitar/incerto continuam ações humanas explícitas, com histórico, sem mutações de Candidate ou Gold.

## FUTURE CAPTURE CONTRACT

app.visual_assets.persist_visual_asset(video_id,bytes,source_metadata) recebe bytes já obtidos legitimamente. source_type:manual_upload,imported_asset,future_capture. Somente os dois primeiros estão no uploadHTTP. Não há caller/captura/runtime TikTok implementado. future_capture é recusado sob security stop; uma futura coleta deverá comprovar permissão/visibilidade antes de fornecer bytes. Dedup persiste o mesmo frame uma única vez.

## TESTS

| Suite | Passed | Task SUCCEEDED |
|---|---|---|
| python | 302 | 2910b39ae89d4cb39e009c55d47fa461 |
| node_dashboard | 118 | 117415b180e644e1aa3067d57e77a17f |

Quatro warnings Python de depreciação preexistentes. API e assetJS locais:200 OK. Testes usam imagens sintéticas/pastas/SQLite temporários; nenhum número desses testes foi contado como resultado real do piloto.

Casos cobertos:upload válido em3formatos;MIME/extensão/conteúdo inválidos;corrupção;limites bytes/dimensões e stream;SHA;dedup e associação;unavailable→available;piloto FN/restrição de escopo;Lens suggested;domain;canonical/aliases;histórico humano;troca de imagem;drag/drop/file picker;corrida de navegação;zero requests TikTok;zero mutação Gold/Candidate.

## PRESERVAÇÃO

{&quot;checked_at&quot;: &quot;2026-10-23T19:13:00.137603+00:00&quot;, &quot;changed_original_tables&quot;: [&quot;events&quot;, &quot;sqlite_sequence&quot;, &quot;system_state&quot;], &quot;changed_existing_files&quot;: [&quot;app\\visual_identification.py&quot;, &quot;app\\visual_identification_api.py&quot;, &quot;app\\static\\visual-identification.js&quot;, &quot;docs\\NEXT_SESSION.md&quot;, &quot;docs\\VISUAL_IDENTIFICATION.md&quot;], &quot;integrity_check&quot;: &quot;ok&quot;, &quot;foreign_key_check&quot;: [], &quot;extension_unchanged&quot;: true, &quot;remote_thumbnail_urls_unchanged&quot;: true, &quot;browser_security_stop_unchanged&quot;: true, &quot;browser_security_history_unchanged&quot;: true, &quot;browser_security_clearance_unchanged&quot;: true}

Schema aditivo sobre visual_image_assets e evidência web, mais tabelas de seleção de asset/sessão assistida. VisualProductEvidence não foi reconstruído. Os dados originais são comparados pelas colunas preexistentes; tabelas operacionais podem variar com heartbeat/restart local. Gold/benchmark,candidates/evidence,classifier/taxonomy/resolver,thumbnails e security history preservados. Sem clear,discovery,Chrome automation,TikTok/CDN requests,supplier scraping ou commit.

## FILES CHANGED

app/visual_assets.py;app/visual_identification.py;app/visual_identification_api.py;app/static/visual-identification.js;requirements.txt;tests/test_local_visual_assets.py;tests/local-visual-assets.test.cjs;docs/LOCAL_VISUAL_ASSETS.md;docs/VISUAL_IDENTIFICATION.md;docs/NEXT_SESSION.md;scripts/local_visual_assets_report.py e artefatos desta pasta.

## NEXT RECOMMENDATION

O usuário vai adicionar imagens reais pelo review. Começar pelo FN4 e seguir a ordem do piloto. Depois clicar IDENTIFICAR PRODUTO, registrar evidência visual/web e avaliar helpful/match/wrong separadamente. Não limpar security stop para obter imagens. Sem uploads reais, nenhuma melhoria de recall pode ser medida.
