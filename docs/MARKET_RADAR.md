# Market Radar

Market Radar é um módulo separado do fluxo TikTok. Ele guarda o que a Babi observou em uma fonte de marketplace em um momento específico; não afirma vendas, popularidade ou histórico que a fonte não forneceu.

## Arquitetura

`app/market_radar/` contém modelos, normalização, repositório SQLite, ranking explicável, scheduler manual, capabilities e adapters. Cada adapter é independente e declara suas próprias capacidades. Nesta fundação todos os adapters são stubs indisponíveis: nenhuma chamada de rede é feita.

## Fontes e confiança

Tipos de fonte: `OFFICIAL_API`, `OFFICIAL_RANKING`, `PUBLIC_PAGE` e `THIRD_PARTY_PROVIDER`. A confiança descreve a fonte (`HIGH`, `MEDIUM`, `LOW`), nunca uma nota do produto. Uma capability matrix declara campos efetivamente suportados, incluindo rank, preço, pedidos, visualizações, avaliações, estoque, URL, imagem, autenticação e API oficial.

## Dados e histórico

- `market_products`: identidade por `marketplace + external_id`.
- `market_snapshots`: o que a Babi observou, com `observed_at`, rank, métricas opcionais, `source_type`, `source_window` e evidência mínima.
- `market_runs`: execução manual e seu resultado.
- `market_source_state`: saúde e capabilities por fonte.

`source_window` é declarado pela fonte. `observation_window` é o período em que a Babi acumulou snapshots. Eles não são equivalentes. `history_available_from` informa a primeira observação real; não há backfill inventado para 1, 3, 7, 15, 30, 60 ou 90 dias.

## Top 20 e movimento

Top 20 é por marketplace e categoria, limitado a 20 e ordenado pelo rank atual da própria fonte. Não há score Babi nem agregação cross-market. Movimento compara snapshots: `NEW_ENTRY`, `UP`, `DOWN`, `STABLE`, `LEFT_TOP` ou `UNKNOWN`, com rank anterior, mudança, primeira e última observação.

Rank, views, orders, sales e preço permanecem suas próprias métricas; o módulo não converte uma em outra.

## Scheduler e adapters

O scheduler atual é somente `manual`; `daily` é apenas uma possibilidade futura. Uma execução sem adapter retorna `UNAVAILABLE` e persiste o run sem simular produtos ou fazer retries agressivos.

Ordem planejada de adapters:

1. Mercado Livre
2. AliExpress
3. Shopee
4. Alibaba
5. SHEIN

## Mercado Livre (MLB)

O primeiro adapter concreto usa somente a API oficial do Mercado Livre e requer
`MERCADO_LIVRE_ACCESS_TOKEN` no ambiente do processo. O token é enviado apenas
no cabeçalho `Authorization: Bearer` e nunca é persistido em SQLite, eventos ou
respostas da API Babi.

- Best sellers: `GET /highlights/MLB/category/{CATEGORY_ID}`. O retorno contém
  no máximo 20 posições oficiais e pode misturar `ITEM`, `PRODUCT` e
  `USER_PRODUCT`.
- Detalhes: `ITEM` usa o endpoint atual `GET /items/bulk`; `PRODUCT` e
  `USER_PRODUCT` usam resolvers independentes. Falhas de detalhe preservam o
  ranking como observação parcial, em vez de descartar a execução.
- Tendências: `GET /trends/MLB[/CATEGORY_ID]` é uma fonte de palavras-chave,
  não de produtos. O adapter persiste 10 `FASTEST_GROWING`, 20 `MOST_WANTED` e
  20 `POPULAR_TREND`, com `source_window=weekly`.

O ranking de best sellers não declara uma janela temporal na resposta, portanto
seu `source_window` permanece ausente. O histórico é exclusivamente composto
pelos snapshots observados pela Babi. `rank` significa posição oficial na
categoria e nunca é convertido em número de vendas.

Uma categoria é validada pelo endpoint oficial no momento da coleta. Rankings
estão disponíveis apenas em algumas categorias folha; uma resposta 404 de
`/highlights` vira `CATEGORY_NOT_RANKED`, não um erro global. O registry Babi
mantém apenas os grupos Casa, Cozinha, Limpeza, Beleza, Moda, Eletrônicos e
Gadgets; IDs folha não são chutados ou espalhados no código.

Endpoints V2:

- `GET /api/v2/market-radar/mercado-livre/top?category=MLB...&period=7d`
- `GET /api/v2/market-radar/mercado-livre/trends?category=MLB...`
- `POST /api/v2/market-radar/mercado-livre/collect`

A coleta é manual, limitada a uma categoria e 20 posições. O status do source
fica como `NOT_CONFIGURED` sem token e `AVAILABLE` depois de uma configuração
válida. Não existe cron, scraping HTML, retry agressivo nem integração TikTok.

### OAuth local

O fluxo local expõe somente endpoints de backend para iniciar OAuth, receber o
callback, renovar token e executar um probe autenticado. O usuário abre e
autoriza a URL manualmente; a Babi não automatiza login. O callback confere um
`state` aleatório e usa PKCE S256. A troca e o refresh enviam segredos no corpo
form-encoded para `/oauth/token`. Tokens são escritos apenas no `.env` local
ignorado e não são retornados por API V2, registrados em banco, logs ou
artifacts. Sem Client ID, Client Secret e Redirect URI a fonte permanece em
`NOT_CONFIGURED`; com app configurado, mas sem autorização, em `AUTH_REQUIRED`.

## Limites desta etapa

Ainda não há Shopee, AliExpress, Alibaba, SHEIN, cron, matching cross-market,
TikTok × marketplace, imagem, embeddings ou alteração no Safety Contract.
