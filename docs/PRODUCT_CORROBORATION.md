# Product Candidate Corroboration + Relationship Discovery

**Semântica atual:** `corroborated` representa suporte lexical legado, não mesma
identidade física. API/UI usam status semântico e confiança de detecção, recorrência
e identidade separados. Ver [PRODUCT_IDENTITY.md](PRODUCT_IDENTITY.md). Fórmula e
histórico abaixo preservados para compatibilidade.

Camada `product-corroboration-v1`, sobre o extrator aprovado `product-candidate-v1`.
Somente dados persistidos; nenhuma coleta, navegação TikTok ou abertura de URL externa.

## Arquitetura e independência

`app/candidate_corroboration.py` centraliza agrupamento, diversidade, confiança e relações.
`app/candidate_gaps.py` registra os gaps e sugestões não resolvidas. Todas as regras,
pesos, limites, termos genéricos e padrões ficam em `config/product_detection.json`.

A migração é aditiva: assinatura no candidate e tabelas de grupos, relações, gaps por
execução, frases não resolvidas, observações dessas frases e decisões de vocabulário.
Candidates, nomes, aliases, evidências, URLs e timestamps anteriores são preservados.
Cada run conserva o snapshot de configuração; a versão de confiança é separada da versão
que originalmente extraiu a evidência.

- Legenda, hashtag, query e links de um vídeo compartilham `video:<id interno>`.
- Bio usa `creator:<id>`. Quando pertence ao creator já representado pelo vídeo,
  o grupo permanece auditável, mas não adiciona uma origem independente.
- Comentário usa `commenter:<username observado>`. Sem autor conhecido não se presume
  independência. Comentários do próprio creator não contam como endosso independente.
- Capturas têm provenance `search_capture:<id>`. Capturas repetidas do mesmo vídeo
  contam como uma única observação independente para diversidade.

`unique_video_count` e `unique_creator_count` continuam representando os vínculos
observados. `independent_video_count` considera somente evidência textual diretamente
atribuída ao vídeo, e `independent_creator_count` conta os usernames observados desses
vídeos. Repetir uma bio em vários vínculos não cria suporte cross-video. Independência
aqui é operacional: não prova ausência de repost, vínculo comercial ou causalidade.

`source_diversity_score` soma componentes limitados de vídeos (35), creators (25),
commenters (20), observações de busca (10) e tipos de evidência de identidade (10),
com alvos configurados 3/3/4/3/3. Quantidade bruta de evidências não entra na fórmula.
É uma métrica descritiva, não probabilidade nem avaliação da qualidade do produto.

## Corroboração e confiança

Uma condição precisa ser satisfeita:

- A: dois vídeos independentes e dois creators distintos observados.
- B: dois vídeos independentes, frase explícita de pelo menos dois tokens e dois
  autores de comentários com dois textos distintos de suporte.
- C: três vídeos independentes, mesmo sem identidade de creator disponível.

A base de identidade é o maior peso de uma fonte, em vez da soma de legenda + hashtag
do mesmo contexto. A legenda continua valendo 0,42. Segundo vídeo adiciona 0,12;
segundo creator, 0,10. Vídeos/creators adicionais têm retornos limitados.
Comentários adicionam passos 0,04/0,02/0,01, limitados por vídeo e globalmente,
deduplicando autores e textos. Query que contém literalmente a frase específica pode
adicionar somente 0,01 de contexto. Queries e links nunca satisfazem corroboração.

Limites: um vídeo 0,49; observado multi-video 0,69; corroborado 0,94. Componentes,
valor antes do limite, limite aplicado, regras atendidas e contagens ficam na API/UI.
Nenhuma métrica de performance social participa. Os valores são heurísticos, não
probabilidades calibradas. Relações entre candidates não transferem confidence.

## Relações sem merge

`candidate_relationships` registra pares ordenados, tipo, score configurado, motivo,
evidências, datas e versão. Descoberta é idempotente. Contexto (`same_video`,
`same_creator`) é exibido separadamente do significado lexical. Compartilhar creator
não significa compartilhar produto.

A relação lexical exige uma combinação de tokens específicos compartilhados e
expansão conservadora por subconjunto, com limite de tokens extras. Palavras genéricas,
frases curtas e números/modelos conflitantes bloqueiam a relação. Exemplo permitido:
`portable dryer` / `portable clothes dryer`; bloqueado: `dish brush` / `floor brush`.
A assinatura remove somente sequências explicitamente configuradas, como o prefixo
`3 in 1`; não elimina números/modelos arbitrários.

Os tipos preparados são `same_normalized_phrase`, `shared_alias`, `lexically_related`,
`same_video`, `same_creator`, `possible_same_product`. A unicidade existente já reúne
a mesma frase normalizada numa hipótese da mesma plataforma, portanto não se criam
arestas de um candidate para si próprio. Aliases genéricos sozinhos não criam relação.
`possible_same_product` exige relação lexical conservadora entre vídeos distintos:
é sugestão para revisão, nunca merge ou confirmação. Scores de relação não são
confidence de identidade. Não há pooling automático entre hypotheses relacionadas.

## Gaps, descoberta e revisão local

Cada execução registra os vídeos processados sem hipótese em `product_detection_gaps`,
com motivo, texto/provenance observado e versão. Categorias: `no_text`, `generic_only`,
`unknown_product_phrase`, `insufficient_evidence`, `noise_filtered`,
`unsupported_language`, `other`. São diagnósticos lexicais auditáveis, não conclusões
sobre o que visualmente aparece no vídeo.

Padrões de grupos nominais e n-grams recorrentes limitados geram
`unresolved_product_phrases`, preservando raw, normalized, signature, vídeo, URL,
texto de origem, método e horário. Capturas duplicadas não simulam recorrência textual.
Não há LLM, parser linguístico ou tradução. A descoberta atual é principalmente
lexical em inglês; escrita latina e árabe não são classificadas como sem suporte
apenas por não terem correspondência no vocabulário.

Revisão local aceita `approved` / `rejected`, preserva histórico e deduplica retries
idênticos. Aprovação registra uma decisão de vocabulário, mas não modifica o detector
ou cria candidate automaticamente. Ativação de novos termos permanece uma alteração
explícita e revisada de configuração. Nenhuma frase real foi aprovada neste sprint.

Endpoints aditivos sob `/api/product-candidates`:

- GET `/relationships`
- GET `/gap-report` (última execução concluída, respeitando seu escopo)
- GET `/unresolved-phrases`
- POST `/unresolved-phrases/{id}/review`, com `decision` e `note` opcional

GET da lista também retorna coverage e frases não resolvidas. O drawer exibe grupos,
diversidade, componentes de confiança, motivo do status e relações navegáveis.
Overview possui diagnóstico recolhível de cobertura/gaps. PT-BR e ar-EG/RTL mantidos.

## Limitações e escopo

Gaps e sugestões têm recall limitado pelos padrões configurados; não identificam
todos os substantivos de todos os idiomas. Perguntas de compra sem termo nominal
inequívoco continuam fora de identidade. Um mesmo produto físico pode originar
hipóteses separadas, e uma frase pode descrever produtos físicos diferentes. Isso é
intencional até existir resolver/clustering revisado. Revisão manual não ativa termos.
Não foram implementados Product final, merge, OCR, visão, IA, preço, marca ou scores
de tendência/performance.

Arquivos deste sprint: `app/candidate_corroboration.py`, `app/candidate_gaps.py`,
`app/product_detection.py`, `app/product_candidate_api.py`,
`config/product_detection.json`, `app/static/index.html`, `scripts/detect_products.py`,
`tests/test_candidate_corroboration.py`, `tests/test_product_detection.py`,
`tests/dashboard-ui.test.cjs` e este relatório. O workspace já continha alterações
anteriores substanciais; elas não foram revertidas nem atribuídas a este sprint.

## Real Library results

Runs 13 and 14: 17 videos, 7 candidates, 0 corroborated, 4 related pairs / 5 relationships, 2 unresolved phrases. Coverage: 6/17 (35.29%); no candidate: 11/17.

All candidates remain observed / 42%, each with one independent group, one independent video, one distinct observed creator and zero supporting commenters.

| Candidate | Raw evidence | Independent groups | Diversity / 100 | Reference |
|---|---:|---:|---:|---|
| Portable Dryer | 3 | 1 | 26.67 | [video](https://www.tiktok.com/@elnazhamai/video/7685436719868464398) |
| 3 in 1 Window Cleaner | 3 | 1 | 26.67 | [video](https://www.tiktok.com/@elnazhamai/video/7643873890845920526) |
| long-handled floor brush | 1 | 1 | 26.67 | [video](https://www.tiktok.com/@tiomi9526/video/7671465879976086797) |
| Burger Patty Maker | 5 | 1 | 26.67 | [video](https://www.tiktok.com/@elnazhamai/video/7670966128629288205) |
| dish brush | 6 | 1 | 26.67 | [video](https://www.tiktok.com/@anya.bumag/video/7665799980480826642) |
| Soap dispenser | 6 | 1 | 26.67 | [video](https://www.tiktok.com/@anya.bumag/video/7665799980480826642) |
| fruit spinner | 2 | 1 | 23.33 | [video](https://www.tiktok.com/@sam.shan.shops/video/7649962108582399253) |

### Real relationships

| A | B | Type | Score | Evidence |
|---|---|---|---:|---|
| Soap dispenser | dish brush | same_creator | 20% | `{"creator_usernames": ["anya.bumag"]}` |
| Soap dispenser | dish brush | same_video | 40% | `{"video_ids": [3]}` |
| Burger Patty Maker | 3 in 1 Window Cleaner | same_creator | 20% | `{"creator_usernames": ["elnazhamai"]}` |
| Burger Patty Maker | Portable Dryer | same_creator | 20% | `{"creator_usernames": ["elnazhamai"]}` |
| 3 in 1 Window Cleaner | Portable Dryer | same_creator | 20% | `{"creator_usernames": ["elnazhamai"]}` |

No lexical or possible_same_product relationships were found. The three @elnazhamai candidates share a creator only. Soap dispenser and dish brush share a video and creator, without physical-product equivalence.

### Detection gaps

| Reason | Videos |
|---|---:|
| no_text | 4 |
| generic_only | 2 |
| unknown_product_phrase | 1 |
| insufficient_evidence | 3 |
| noise_filtered | 1 |
| unsupported_language | 0 |
| other | 0 |

| Internal video ID | Persisted caption | Reason | URL |
|---:|---|---|---|
| 1 | Easy to remove the stains😏 #gadgets | unknown_product_phrase | [video](https://www.tiktok.com/@airlandolists/video/7462746836533677358) |
| 2 | Easy to clean kitchen😏 #gadgets | insufficient_evidence | [video](https://www.tiktok.com/@airlandolists/video/7537701539553496334) |
| 4 | 🔗Link in bio. Amazon Home Finds | noise_filtered | [video](https://www.tiktok.com/@goodfinds366/video/7688040645037952278) |
| 5 | null | no_text | [video](https://www.tiktok.com/@bk_owner/video/7505858880568691970) |
| 6 | Você esqueceu de desconectar? | insufficient_evidence | [video](https://www.tiktok.com/@megashopping39/video/7672558839388048661) |
| 7 | null | no_text | [video](https://www.tiktok.com/@home.gadgets17/video/7689057449575337238) |
| 8 | null | no_text | [video](https://www.tiktok.com/@airlandolists/video/7660555038258924814) |
| 11 | null | no_text | [video](https://www.tiktok.com/@dreambunny22/video/7628036818079976735) |
| 12 | Easy to dry clothes in house😏 #gadgets | insufficient_evidence | [video](https://www.tiktok.com/@airlandolists/video/7698002338652507405) |
| 14 | 🔗In Bio! Kitchen Gadgeg I Use Daily🥚🤍 | generic_only | [video](https://www.tiktok.com/@elnazhamai/video/7639794804339019022) |
| 17 | #Tecnologia #futuro | generic_only | [video](https://www.tiktok.com/@jornadatop/video/7698829746569858311) |

### Unresolved phrases

Both phrases come from comments on the @airlandolists stain-removal video. These are unverified lexical suggestions, not visually identified products.

- **vacuum cleaner**: `pending`; [video](https://www.tiktok.com/@airlandolists/video/7462746836533677358).
  - Raw: "vacuum cleaner"; observed 2026-10-21T18:35:07.782041+00:00; `comment_observations:visible:63f7660405bd00c8654ca39b943c0a4c3cbb1a5b07ec9ede9f3d7079dc20666e`.
  - Raw: "vacuum cleaner"; observed 2026-10-21T18:46:35.610448+00:00; `comment_observations:visible:0f7ce80a38442babbe2be8d520a76d70ac0102290c877e8ea090ca973f9d9fb3`.
  - Raw: "Mini Vacuum Cleaner Price? very useful ✨"; observed 2026-10-21T18:46:35.610448+00:00; `comment_observations:visible:2b5d739096aec36acc714367ce7db88f8c51d93b7a6ceffe63181bf356999a5d`.

- **Mini Vacuum Cleaner**: `pending`; [video](https://www.tiktok.com/@airlandolists/video/7462746836533677358).
  - Raw: "Mini Vacuum Cleaner Price? very useful ✨"; observed 2026-10-21T18:46:35.610448+00:00; `comment_observations:visible:2b5d739096aec36acc714367ce7db88f8c51d93b7a6ceffe63181bf356999a5d`.

### Idempotency and preservation

{"candidate_records_unchanged": true, "relationship_records_unchanged": true, "unresolved_records_unchanged": true, "no_new_candidates": true, "no_new_evidence": true}

Rerun creates zero additional candidates, evidence, relationships or unresolved phrases. Candidate, relationship and unresolved records compare identically. Only run/gap audit history gains a new run.

Hashes confirm unchanged source data: 17 videos, 32 search observations, 18 detail observations, 9 samples / 149 comments, 8 creators / 20 profile observations, 26 evidence rows, 7 aliases and 26 URL relations. Candidate IDs, status, confidence, first_seen and primary reference also remain unchanged.

Full validation: `data/product_detection_validation.json`. Preservation audit: `.runtime/corroboration-preservation.json`. Pre-migration SQLite backup: `data/product_hunter.pre_corroboration.db`. These local data artifacts are not committed.

## Final validation

