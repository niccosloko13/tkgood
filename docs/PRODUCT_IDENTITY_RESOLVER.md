# Product Identity Resolver v1 — offline

Versão `product-identity-resolver-v1`, 22/10/2026. Apenas dados persistidos.
Nenhuma Product entity, merge, navegação, enrichment ou confirmação de identidade.

## Arquitetura e compatibilidade

`app/product_identity_resolver.py` separa adaptação de ocorrências, geração de pares,
features, score/decisão e persistência. Configuração em `config/product_identity.json`,
seção `resolver`; pesos e thresholds antigos de detecção/recorrência não mudaram.

Migração aditiva amplia `product_identity_pairs`: id estável, candidate/occurrence/video
IDs, identity_score, semantic_result, reason, evidence_json, resolver_version e created_at.
Campos existentes, seus valores e pares legados são preservados. Campos novos dos
pares legados ficam null; não representam avaliações do novo resolver.
`id` é identificador textual determinístico com índice único; pair_key permanece PK.
created_at é preservado; comparação igual não altera updated_at nem duplica linhas.

Rows resolver têm prefixo `resolver:` e versão própria. Não misturar escalas:
identity_score e concept_similarity_score do resolver são 0–100; campos legados
`product_identity_score` mantêm escala 0–1. Listagem antiga de identity-pairs retorna
somente pares legados. API nova separa as avaliações do resolver.

Candidate semantic_status/detection_confidence/recurrence_confidence/identity_confidence
anteriores não são sobrescritos pelo resolver. O resultado pertence ao **par**:
`different`, `insufficient`, `possible_same_product`. Nunca same_product confirmado.
Mesmo uma hipótese positiva não promove o candidate, não propaga transitivamente
identidade e não faz merge. Novos detection runs incluem comparação local ao final;
nenhum detection run real foi necessário para esta validação.

## Ocorrências reais e geração limitada

Uma ocorrência é candidate + vídeo, com extracted phrases/aliases observados nesse
contexto, captions históricas, creator, video URL, IDs de evidência, URLs contextuais
e comentários já persistidos. Aliases globais nunca são atribuídos a todos os vídeos.
Quando há várias frases locais, a comparação selecionada e todas as alternativas
permanecem em evidence_json. Comentários históricos repetidos são deduplicados por
author/text; quantidade não multiplica contribuição.

Índice invertido usa mesmo candidate, tokens específicos e sequências de 2–4 tokens
observadas; relações existentes entre candidates também geram pares. Isso permite
portable blender ↔ mini portable blender sem unir hypotheses. Bare heads genéricos
de candidates distintos não geram comparação cega de todos com todos.
Limites: 100 ocorrências por bucket, 1000 pares por execução. Truncamento é declarado,
nunca apresentado como cobertura integral. No corpus atual não houve truncamento.

## Features e decisão

Cada feature persiste value, weight, contribution e explanation. Além da frase,
somente modificadores configurados e bundles numéricos dentro de oito tokens do
head na caption são aproveitados. Não se coleta texto novo nem se extraem preços.

| Feature | Peso máximo |
|---|---:|
| Frase normalizada exata com ≥2 tokens específicos | +30 |
| Sobreposição de tokens específicos, proporcional | +20 |
| Modificadores compartilhados, limitado | +20 |
| Head genérico compartilhado | 0 |
| Números explicitamente iguais | +5 |
| Dimensões explicitamente iguais | +10 |
| ≥2 tokens explícitos brand-like compartilhados | +35 |
| Tokens model-like alfanuméricos explícitos | +25 |
| URL de listing exata e ligada à frase em cada origem | +75 |
| Referência externa contextual | 0 |
| Características específicas em comentários das duas origens | +10 |
| Modificadores fracos compartilhados | +5 |
| Modificadores conflitantes configurados | −50 |
| Números/dimensões/model-like conflitantes | −60 cada |
| Especialização não compartilhada | −8 |

Brand-like significa tokens capitalizados não genéricos escritos nas frases; não
há identificação de brand/model, catálogo ou inferência de marca não escrita.
Dimensões preservam decimais/unidades; não há conversão de unidades. Bundles como
3-in-1 não são classificados como modelos. Falta de número numa origem não é conflito.

Score é soma, floor 0, cap 100. Sem ≥2 tokens específicos compartilhados com head
compatível ou listing explicitamente igual, cap 39. Mesmo vídeo ou conflito explícito
também impõem cap 39. Assim head genérico e comentários contextuais não bastam.

- ≥70: possible_same_product;
- <40 e evidência negativa explícita: different;
- demais: insufficient, incluindo 40–69.

`different` é indicação heurística de conflito, não verdade física confirmada.
0 não prova diferença. Scores não são porcentagens de probabilidade.
Creator distinto não soma pontos ao score de identidade; sua provenance é preservada.

URLs: creator_profile e profile_link nunca contam como listing. commercial_link,
external_link ou exact_listing_url exigem binding explícito via extracted_text,
HTTPS, path configurado e host não excluído. Match usa URL exata, preservando query/SKU.
URL comercial genérica/bio/redirect é apenas contexto. Não se abre/verifica listing.

## Resultado real

45 vídeos, 8 candidates e 65 evidências preservados. Nove ocorrências de candidates.
**5 pares avaliados: 0 different, 5 insufficient, 0 possible_same_product.**
Todos os possíveis matches: nenhum. Top 5, incluindo scores abaixo do threshold:

| Par | Vídeos Library | Identity /100 | Decisão |
|---|---|---:|---|
| escova ↔ escova | 39 / 40 | 10 | insufficient |
| 3 in 1 Window Cleaner ↔ Portable Dryer | 15 / 16 | 0 | insufficient |
| Soap dispenser ↔ dish brush | 3 / 3 | 0 | insufficient |
| Burger Patty Maker ↔ 3 in 1 Window Cleaner | 9 / 15 | 0 | insufficient |
| Burger Patty Maker ↔ Portable Dryer | 9 / 16 | 0 | insufficient |

Os quatro últimos são avaliações de vínculos legados, não prova de semelhança.
Soap dispenser e dish brush no mesmo vídeo podem descrever componentes; não inferir merge.

### Escova

Occurrence A: candidate 8 / vídeo 39 / **@isadoravalebr**.
Caption: “Essa escova elétrica gira sozinha e ajuda a limpar rejunte, cantos e sujeira grudada sem tanto esforço.”
Extracted phrase e alias local: `escova`.
https://www.tiktok.com/@isadoravalebr/video/7657730138993446151

Occurrence B: candidate 8 / vídeo 40 / **@vitrineglei**.
Caption: “escova elétrica 9 em 1, limpeza profunda, cabo extensível, banheiro, cozinha, piso, box e rejunte”.
Extracted phrase e alias local: `escova`.
https://www.tiktok.com/@vitrineglei/video/7673992589036506388

Compartilhado: frase normalizada escova e head genérico escova (zero pontos),
modificador contextual `elétrica` (+10 por apenas um modificador compartilhado).
Sem tokens específicos na frase, listing igual ou supporting comments.
Divergência contextual: B explicita `9 em 1` e `extensível`; A não. Número ausente
em A não é conflito nem confirmação numérica. Nenhum atributo/modelo exclusivo igual.
Conceito 100/100, identidade **10/100 — insufficient**. Candidate continua
concept_recurring; detecção 42%, recorrência 60%, identidade legada 0; não substituir
essas dimensões pelo score do par. Legado corroborated/64% também permanece intacto.

### Unresolved

vacuum cleaner ↔ Mini Vacuum Cleaner: **30/100, insufficient**. Vacuum compartilhado
é +20 de token específico e +10 de modificador único. Mini só em uma origem indica
frase mais específica, não mesma identidade. Ambos pertencem ao mesmo vídeo; cap 39.
Comparação diagnóstica no relatório, sem criar candidate/pair com FK inventada ou
promover/aprovar frases. Ambas continuam pending.

## API, UI e operação local

GET `/api/product-candidates/resolver-pairs`; GET `/resolver-pairs/{id}`;
POST `/api/product-candidates/resolve-identity` executa só comparação SQLite.
Candidate API inclui resolver_pairs e possible_identity_matches separadamente.
Drawer PT-BR/ar-EG mostra quantidade de possíveis matches, score /100, decisão,
“Não mesclado”, breakdown expansível, captions/creators/URLs/provenance e versão/datas.

```
.\.venv\Scripts\python.exe scripts/resolve_product_identity.py --apply
.\.venv\Scripts\python.exe scripts/resolve_product_identity.py
.\.venv\Scripts\python.exe scripts/background_runner.py pytest
.\.venv\Scripts\python.exe scripts/background_runner.py node-tests
```

Default RO, --apply migra/resolve apenas localmente. Artefatos:
data/product_identity_resolver_report.json, resolver_before/after.json,
resolver_verification.json e backup product_hunter.pre_resolver.db.
Logs em .runtime/logs; backend somente pode ser reiniciado via devctl restart-backend,
sem reload de Companion/TikTok. Security stop HTTP403 permanece ativo.

Limitações: vocabulário/case de brand-like e janelas lexicais são heurísticos;
captions podem descrever vários itens; URL não foi validada externamente. Sem IA,
embeddings, OCR, visual, preço, Product final, merge ou identidade confirmada.
Validação final e checkpoint em NEXT_SESSION.md. Sem navegação/engagement/commit.
