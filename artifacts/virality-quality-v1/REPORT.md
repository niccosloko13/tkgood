# BABI — Virality + Quality Intelligence v1

Concluído com dados locais. Nenhuma navegação/request TikTok, download de CDN,
provider visual, busca web ou consulta a fornecedor foi executada nesta sprint.
Nenhum commit. Security stop e histórico do incidente permanecem intactos.

## Dimensions implemented

O read model existente do Intelligence Core foi ampliado com oito dimensões
versionadas. Identity Resolver, Decision Gate e estruturas de evidência foram
preservados. O contrato legado `quality` permanece compatível; a UI usa
`intelligence.dimensions`, sem reescrever evidências históricas de decisões.

| Dimensão | measured | partial | insufficient_data |
|---|---:|---:|---:|
| Purchase Intent | 4 | 2 | 39 |
| Signal Quality | 0 | 41 | 4 |
| Viral Potential | 0 | 41 | 4 |
| Creative DNA | 0 | 41 | 4 |
| Product Quality | 0 | 5 | 40 |
| Saturation | 0 | 45 | 0 |
| Trend Readiness | 0 | 0 | 45 |
| Commercial Readiness | 0 | 2 | 43 |

Cada dimensão inclui status, classificação, coverage, sample_size, unique_sources,
confidence_status, reason_codes e evidence_ids. Contagens observadas podem ser
zero; resultados desconhecidos, ratios sem amostra e features sem suporte ficam
null/insufficient. Não há Opportunity, Winner, Gold ou Viral Score agregado.

## Pilot videos

Executados primeiro: **1, 3, 18, 9, 10, 13, 15**. A lista combina os três IDs
solicitados com os seis REVIEW reais, sem duplicar 1 e 3. Depois foram analisados
os 45 vídeos. Identity antes e depois: **AUTO 0 / REVIEW 6 / UNRESOLVED 39**.
Nenhuma nova entidade, revisão humana ou classificação de identidade foi criada.

| Vídeo | Identity | Comentários únicos | Autores | Autores com intenção | Purchase Intent |
|---|---|---:|---:|---:|---|
| 1 | REVIEW | 34 | 32 | 26 | STRONG / measured |
| 3 | REVIEW | 30 | 30 | 22 | STRONG / measured |
| 18 | UNRESOLVED | 19 | 19 | 6 | MODERATE / measured |
| 9 | REVIEW | 0 | 0 | 0 | Sem amostra |
| 10 | REVIEW | 0 | 0 | 0 | Sem amostra |
| 13 | REVIEW | 0 | 0 | 0 | Sem amostra |
| 15 | REVIEW | 0 | 0 | 0 | Sem amostra |

O vídeo 18 prova a independência de Identity: intenção e reclamação são extraídas
mesmo com identidade não resolvida. A categoria existente continua independente.

## Purchase intent results

V2 reutiliza as regras de consumer signals e adiciona classes separadas PT/EN/ES:
WHERE_TO_BUY, LINK_REQUEST, PRICE_QUESTION, WANT, NEED, PURCHASE_DECLARATION,
AVAILABILITY_QUESTION. A versão usada nas decisões históricas não foi alterada.

Deduplicação: autor normalizado + texto normalizado, mesmo quando o comment_id
aparece apenas em algumas capturas. Cópias anônimas de texto já atribuído não
adicionam demanda. Autores diferentes pedindo o mesmo link continuam distintos;
um autor em várias classes conta apenas uma vez no total de autores com intenção.
IDs de todas as observações capturadas permanecem na proveniência.

| Vídeo com comentários | Amostra única | Autores únicos | Autores com intenção | Classe | Cobertura |
|---|---:|---:|---:|---|---|
| 1 | 34 | 32 | 26 | STRONG | measured |
| 3 | 30 | 30 | 22 | STRONG | measured |
| 6 | 8 | 7 | 1 | WEAK | partial |
| 12 | 6 | 6 | 2 | MODERATE | partial |
| 18 | 19 | 19 | 6 | MODERATE | measured |
| 39 | 30 | 29 | 6 | MODERATE | measured |

Total: 2 STRONG, 3 MODERATE, 1 WEAK, 39 sem amostra. Não são vendas estimadas.
Não somar classes como demanda independente: o mesmo autor pode aparecer em várias.

Exemplos do painel Por quê:

- Vídeo 1: 12 autores pediram link, 5 perguntaram onde comprar, 1 perguntou preço;
  26 autores com intenção no total; ratio por comentário 26/34 = 76,47%.
- Vídeo 3: 8 pediram link, 7 perguntaram onde comprar, 1 perguntou preço;
  22 autores com intenção; ratio 22/30 = 73,33%.
- Vídeo 18: 6 autores com intenção em 19 comentários = 31,58%; MODERATE.

STRONG exige ao menos 10 comentários únicos, 70% de cobertura de atribuição,
5 autores com intenção e 35% dos autores amostrados. MODERATE exige 2 autores
e 15%. São critérios operacionais explícitos, não probabilidades.

## Signal quality

Mantida separada de intenção, identidade e qualidade. A evidência por vídeo depende
de um único vídeo/criador; creator_diversity permanece null quando só há um criador.
O painel mostra commenter diversity, repetição de capturas, fontes locais,
dependência e duração entre observações. Essa duração não é vida de mercado.

Contar caption, comentários e provider visual como canais não estabelece fontes
independentes externas. Cross-source agreement permanece null sem confirmação.
Apenas ocorrências de entidades aprovadas podem ampliar o escopo de produto;
recorrência de candidate não faz esse join. Nenhum produto foi associado por
similaridade nesta sprint.

## Creative DNA and viral features

Campos estruturados de hook, problema, solução, demonstração, payoff, transformação,
visibilidade inicial, duração, CTA, before/after, ASMR, momento satisfatório,
formato repetível e ângulos estão disponíveis com status e evidência.

Caption de função/CTA fornece sinal partial. Observações visuais já persistidas
podem suportar visibilidade do produto/demonstração, sem nova inferência. Uma imagem
estática não comprova timing inicial, transformação em vídeo, novidade de mercado,
wow factor, shareability, ASMR ou performance do criativo. Esses campos permanecem
insufficient quando não há evidência apropriada.

Creative Repeatability tem features separadas de casos de uso, ângulos de problema
e demonstração, comparação, teste, reação, before/after e satisfying demo. HIGH
exige três features explicitamente observadas; MEDIUM exige duas suportadas.
Uma única pista parcial na caption não vira LOW por falta de dados. No conjunto
atual, **45 INSUFFICIENT**, sem HIGH artificial.

Viral Potential mantém onze features independentes e razões. A intenção de compra
pode estar observada enquanto hook, novidade e transformação seguem insuficientes.
Product Signal e Creative Signal aparecem em grupos distintos no dashboard.

## Product quality signals

Classes separadas: reações positivas/negativas, reclamações de produto/qualidade,
DOES_NOT_WORK, BROKE, FAKE, USEFUL, EASY_TO_USE e HARD_TO_USE.

| Vídeo | Autores positivos | Autores negativos | Autores com reclamação | Resultado |
|---|---:|---:|---:|---|
| 1 | 6 | 0 | 0 | INSUFFICIENT_DATA / partial |
| 3 | 5 | 0 | 0 | INSUFFICIENT_DATA / partial |
| 18 | 0 | 0 | 1 | INSUFFICIENT_DATA / partial |
| 39 | 2 | 1 | 1 | MIXED / partial |

Negativos e reclamantes podem se sobrepor. MIXED descreve relatos contraditórios,
não qualidade verificada. Nenhum PROMISING/CONCERNING foi emitido. A política exige
30 comentários, 15 autores, dois vídeos confirmados e dois criadores, além das
regras de positivos/reclamações. Uma reação “útil” não comprova uso ou durabilidade.

## Saturation and trend readiness

Todos os 45 ficam LOCAL_EVIDENCE_ONLY em Saturation. São contagens locais, hints
de recorrência de candidate/query e dependência de criador; não saturação de mercado.

**45 INSUFFICIENT_HISTORY** em Trend. Datas de captura repetidas não bastam para
velocidade. Readiness exige três observações numéricas distintas de engajamento
ao longo de 24h. Labels da UI como “Curtida” não são números.

A estrutura mantém first_seen/last_seen, contagens diárias de comentários e intenção
deduplicados na primeira captura local e observações numéricas reais, quando
existirem. Datas não são tratadas como publicação/atividade do consumidor.
videos_per_day, unique_creators_per_day, engagement_velocity,
creator_acceleration e change_point ficam null sem cobertura apropriada.

## Commercial readiness

**2 PARTIAL (1 e 3), 43 NOT_READY, 0 READY_FOR_SUPPLIER_DISCOVERY**.
Flags individuais: identidade aprovada, intenção forte medida, cobertura positiva
de qualidade, confirmação visual, dados de fornecedor e preço. Imagem não é requisito
universal para identidade textual. Dados de fornecedor/preço não são pré-requisitos
circulares para iniciar pesquisa, mas ficam explicitamente ausentes.

Não houve Supplier Discovery, scraping ou estimativa de margem/preço.

## Dashboard and persistence

O painel `/intelligence-core` mostra as oito dimensões, Por quê, amostra, autores,
referências de evidência e detalhes de cobertura recolhidos. Filtros:
Strong Purchase Intent, High Creative Repeatability, Product Quality Concern,
Needs More Data, Ready for Supplier Discovery e Review Identity. São filtros
booleanos, sem ranking final. A fila humana continua exclusiva de REVIEW.

135 snapshots históricos correspondem a três revisões locais de desenvolvimento
dos 45 itens; não são 135 vídeos ou novas coletas. O estado final contém os 45
itens. Repetir o processamento com o mesmo resultado não acrescenta snapshots,
verificado no piloto e na biblioteca. Histórico intermediário foi preservado.

API local: HTTP 200, 45 itens com as oito dimensões, quatro itens com Purchase Intent
measured; leitura completa em 3,703s nesta máquina. HTML e JavaScript também
responderam HTTP 200. Nenhum modelo pesado foi carregado pela nova análise.

## Preservation

Checkpoint anterior ao código: `checkpoint.db`. Comparação em `results.json`:
67 tabelas anteriores inspecionadas; 65 idênticas. As duas com atividade permitida
são events e system_state (operação/heartbeat). As linhas específicas
browser_security_stop e browser_security_history são exatamente iguais.

Gold Set, candidates, evidências, assets, categorias, decisões, entidades, reviews,
índice e embeddings permaneceram iguais ao checkpoint. Nenhuma alteração de
browser runtime. Somente backend reiniciado pelo Dev Control existente.

## Tests

- Regressão completa Python: **412 passed**, sete avisos de depreciação existentes,
  zero falhas. Task `6ca416bddc804cbba6b5e0c1196fcd48`.
- Regressão completa Node/dashboard final: **123 passed**, zero falhas/skips.
  Task `d072e9438f374917a84d7e688839532a`.
- Verificação Python focada após ajustes finais de apresentação/contrato:
  **94 passed** (analytics, activation e Core).
- 32 novos casos Python e um novo teste comportamental de dashboard.
- Cobertura adicionada: PT/EN/ES, dedup de autor/captura/IDs parciais, negação,
  complaints, dependência de criador, identidade independente, still sem timing
  inventado, repeatability, histórico numérico, prontidão sem dependência circular
  de fornecedor, snapshots idempotentes, ausência de rede e isolamento de Gold.
- A verificação real do checkpoint confirma preservação do security stop e tabelas
  de negócio. Uma regressão temporária no fallback de apresentação legado foi
  corrigida; a suíte Node final completa passou, sem alterar testes existentes.

## Files changed in this sprint

- `app/comments.py`: consumer signals v2; versão antiga preservada.
- `app/intelligence_signals.py`: dimensões offline, proveniência e snapshots.
- `app/intelligence_core.py`: read model e contador de intenção medido em v2.
- `app/static/intelligence-core.html` e `.js`: dimensões, explicações e filtros.
- `config/virality_quality.json`: política central.
- `scripts/virality_quality.py`: piloto, materialização e verificação do checkpoint.
- `tests/test_virality_quality.py`, `tests/virality-quality.test.cjs`.
- `docs/VIRALITY_QUALITY.md` e artefatos desta pasta.

## Limitations and next recommended sprint

Há comentários em apenas seis vídeos e uma imagem local. Padrões lexicais não
resolvem sarcasmo, bots, identidade real dos autores nem experiência de compra.
Classes e thresholds precisam de avaliação humana separada antes de decisões
comerciais; Gold de identidade não é referência de sentimento ou de qualidade.

Próximo sprint recomendado: avaliar consumer signals e Creative DNA com amostras
locais revisadas, sem contaminar o Gold de identidade; incorporar assets fornecidos
manualmente e evidências temporais legítimas quando disponíveis. Priorizar cobertura
e calibração por dimensão. Manter TikTok parado enquanto o security stop estiver
ativo. Não criar ranking final com a cobertura atual.
