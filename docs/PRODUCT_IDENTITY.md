# Recorrência de conceito e identidade de produto

**Resolver atual:** comparação de ocorrências com score /100 e decisão pairwise em
[PRODUCT_IDENTITY_RESOLVER.md](PRODUCT_IDENTITY_RESOLVER.md). Não substitui status ou
dimensões do candidate; o conteúdo abaixo documenta a foundation preservada.

Sprint offline, 22/10/2026. Versão `product-identity-foundation-v1`.

`corroborated` e `confidence` são campos **legados**, não confirmação de identidade
física. Permanecem intactos; API também expõe `legacy_status`/`legacy_confidence`.
Consumidores devem usar `semantic_status`: `observed`, `concept_recurring`,
`possible_same_product`; `product_matched` é reservado e nunca atribuído automaticamente.

## Arquitetura

`app/candidate_semantics.py` implementa assinaturas conservadoras e pares.
`config/product_identity.json` centraliza termos genéricos, pesos, caps e condições.
A configuração e as fórmulas legadas de detecção/corroboration não mudaram.

Migração aditiva: `candidate_semantics`, `candidate_semantic_history`,
`product_identity_pairs`, `product_identity_evidence`. Histórico guarda score/status
anteriores, motivo, snapshot, fingerprint e timestamp. Recálculo igual não duplica
pares/sinais/histórico. Nenhum candidate/evidence/alias/URL/run anterior é apagado.

GET `/api/product-candidates` e `/{id}` incluem dimensões, assinatura, pares e histórico.
GET `/api/product-candidates/identity-pairs` expõe os pares. Detection runs futuros
atualizam a projeção após a pipeline existente e ganham `semantic_status_counts` e
`legacy_corroborated_count`. Nenhum detection run real foi executado neste sprint.

## Dimensões separadas

- Detecção: componente base persistido de extração, sem bônus de recorrência.
- Recorrência: segundo vídeo +35 pontos; segundo creator +25; adicionais +10 cada;
  cap 95. Um vídeo tem zero suporte de recorrência, mesmo com muitas evidências.
- Identidade: sinais específicos entre ocorrências; sem métricas sociais.
- Especificidade: head genérico 5 pontos; modificador específico +25; fracos têm
  pesos próprios; bundles +15; médio ≥30, alto ≥65. Não é confiança.

São heurísticas de suporte, **não probabilidades calibradas**. Identidade zero
significa insuficiência, não prova de produtos diferentes. Recorrência 60% não é
redução do legado 64%: são dimensões distintas. Creators distintos são usernames
observados; não comprovam independência comercial ou causalidade.

Assinatura preserva raw/normalized phrase, head, modificadores, tokens genéricos,
números/modelos textuais e bundles. Não extrai brand/model ou traduz; head desconhecido
recebe especificidade zero. Não há NLP complexo, LLM, stemming, visual ou OCR.

Pares de ocorrências usam extracted_text realmente observado em cada vídeo,
não atribuem alias global a todas as origens. Caption/hashtag/metadado deve existir
em ambas. Frase exata altamente específica com ≥2 modificadores específicos tem
75 pontos, +10 por modificadores compartilhados. Alias forte exige compatibilidade
de head/modificadores/números. Números conflitantes impedem o sinal textual.
Possível correspondência exige ≥2 vídeos/creators distintos e score ≥75.

URL só contribui como `external_link` explicitamente ligado à frase pelo extracted_text,
HTTPS e path de listing configurado. Links de perfil/bio/redirect não contam. SKU/query
significativa é preservada; só utm_* e fragmento saem da comparação. Nenhum link é aberto.
URL igual gera hipótese possível, nunca confirmação automática.

Pares entre candidates relacionados têm scores separados e não promovem status
automaticamente: falta validar suas ocorrências. Suporte pairwise dentro de um
candidate não afirma que todos seus vídeos representam o mesmo produto. Sem propagação
transitiva, merge, clustering ou Product final. Sinais futuros estão reservados em config.

## Resultado real

45 vídeos; 8 candidates; 65 evidências; 2 unresolved phrases pending.

| Candidate | Detecção | Recorrência | Especificidade /100 | Identidade | semantic_status |
|---|---:|---:|---:|---:|---|
| Soap dispenser | 42% | 0% | 30 · média | 0% | observed |
| dish brush | 42% | 0% | 30 · média | 0% | observed |
| Burger Patty Maker | 42% | 0% | 55 · média | 0% | observed |
| fruit spinner | 42% | 0% | 30 · média | 0% | observed |
| long-handled floor brush | 42% | 0% | 55 · média | 0% | observed |
| 3 in 1 Window Cleaner | 42% | 0% | 45 · média | 0% | observed |
| Portable Dryer | 42% | 0% | 35 · média | 0% | observed |
| escova | 42% | 60% | 5 · baixa | 0% | concept_recurring |

7 merely observed; 1 recurring concept; **0 possible same-product matches**;
0 product matched. Demais candidates têm um vídeo/creator independente.
Quatro pares de candidates relacionados e um par entre ocorrências de escova;
todos com identidade zero. Grafo legado preservado.

### Escova — fixture real

Vídeo 39, **@isadoravalebr**:
“Essa escova elétrica gira sozinha e ajuda a limpar rejunte, cantos e sujeira grudada sem tanto esforço.”

https://www.tiktok.com/@isadoravalebr/video/7657730138993446151

Vídeo 40, **@vitrineglei**:
“escova elétrica 9 em 1, limpeza profunda, cabo extensível, banheiro, cozinha, piso, box e rejunte”

https://www.tiktok.com/@vitrineglei/video/7673992589036506388

Ambos: extracted/normalized phrase `escova`; alias `escova`; specific tokens `[]`;
generic tokens `[escova]`; head escova. Seis captions históricas, grupos `video:39`
e `video:40`, zero supporting comments. Conceito 100%; identidade 0%.
As captions sugerem limpeza elétrica, mas não estabelecem listing/modelo/atributos
exclusivos iguais. O extrator não preservou uma frase mais específica: não fabricamos
aliases nem inferimos identidade do nome amplo. Resultado `concept_recurring`.
Legado `corroborated`, 64%, broad_concept=true intacto e auditável.

Fixture `tests/fixtures/product-identity-escova.json` preserva captions, creators,
evidências, grupos, aliases e URLs reais, sem qualquer nova navegação.

`vacuum cleaner`: 30/100; `Mini Vacuum Cleaner`: 50/100. Mini acrescenta especificidade
fraca; ambas continuam médias/pending. Sem aprovação/auto-learning/candidate novo.
Continuam um vídeo, dois autores/textos distintos, com repetição histórica de um comentário.

## Operação e preservação

```
.\.venv\Scripts\python.exe scripts/product_semantics_report.py
.\.venv\Scripts\python.exe scripts/product_semantics_report.py --apply
.\.venv\Scripts\python.exe scripts/background_runner.py pytest
.\.venv\Scripts\python.exe scripts/background_runner.py node-tests
```

Default: SQLite read-only. --apply: só tabelas semânticas e marcador. Não executa
detection/enrichment. Backup `data/product_hunter.pre_semantics.db`; relatório
`data/product_semantics_report.json`; auditoria `data/semantics_verification.json`.
Backend reiniciado silenciosamente pelo devctl; Companion/TikTok não recarregados.
Logs `.runtime/logs`; HTTP403/security stop preservado. Sem navegação/comando TikTok,
engagement ou commit. Renderização DOM PT-BR/ar-EG testada sem abrir navegador.

Limites: vocabulário lexical limitado, heurísticas sem calibração, sem validação de
marketplace/atributos estruturados. Nenhum score confirma identidade física.
Validação final e checkpoint em NEXT_SESSION.md.
