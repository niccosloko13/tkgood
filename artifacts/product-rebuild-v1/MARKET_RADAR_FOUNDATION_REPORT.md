# Market Radar Foundation — Etapa 7

## Arquitetura

Criado `app/market_radar/` como módulo isolado do fluxo TikTok: modelos, capabilities, normalização, repositório, ranking, serviço, scheduler manual e adapters. Não há adapter concreto nem chamada de rede.

## Migrations e persistência

`db.init_db()` agora cria, de forma idempotente:

- `market_products`: identidade por `marketplace + external_id`;
- `market_snapshots`: evidência observada no momento, com métricas opcionais;
- `market_runs`: execuções manuais e seus resultados;
- `market_source_state`: disponibilidade, capabilities e saúde de fonte.

A migration foi aplicada ao banco existente pelo supervisor sem alterar dados TikTok.

## Contratos

- `MarketplaceAdapter` declara capabilities e `fetch_top_products`.
- Capability matrix cobre rank, categoria, preço, vendas, pedidos, visualizações, avaliações, estoque, fornecedor, MOQ, source window, URL, imagem, autenticação e API oficial.
- Source types: `OFFICIAL_API`, `OFFICIAL_RANKING`, `PUBLIC_PAGE`, `THIRD_PARTY_PROVIDER`.
- Source confidence descreve somente a fonte (`HIGH`, `MEDIUM`, `LOW`).
- Stubs: Mercado Livre, AliExpress, Shopee, Alibaba e SHEIN.

## Snapshot, histórico e Top 20

- Snapshots preservam dados ausentes como nulos; não convertem rank em vendas ou visualizações em pedidos.
- `source_window` e `observation_window` permanecem distintos.
- Histórico retorna apenas observações reais e informa `history_available_from`.
- Movimento é explicável por rank: `NEW_ENTRY`, `UP`, `DOWN`, `STABLE`, `LEFT_TOP`, `UNKNOWN`.
- Top 20 é limitado a 20 e ordenado pelo rank da própria fonte. Não há score Babi ou agregação entre marketplaces.

## Scheduler e API

- Scheduler foundation: modo `manual`; `daily` é apenas possibilidade futura, não foi ativado.
- `run_marketplace_collection` retorna `UNAVAILABLE` sem adapter e registra o run, sem inventar produtos ou repetir tentativas.
- `GET /api/v2/market-radar` e `GET /api/v2/market-radar/sources` expõem apenas read models sem tabelas, segredos ou exceções brutas.
- Sistema V2 lê as cinco fontes cadastradas em `Fontes externas`; todas aparecem corretamente como não configuradas.

## Validação

- Python: `33 passed` (`test_market_radar.py`, `test_api_v2.py`, `test_trend_engine_v2.py`).
- JavaScript geral: `177 passed`.
- UI V2: `7 passed`; `npm run check` e `npm run build` passaram.
- Backend reiniciado pelo supervisor: saudável.
- Endpoints reais retornaram 5 fontes, todas `NOT_CONFIGURED`; Sistema V2 retornou as mesmas 5 fontes.

## Limitações e próximo passo

Nenhum marketplace foi integrado, não há cron, scraping, autenticação, matching cross-market, ligação TikTok × marketplace, embeddings ou nova UI de radar. O próximo passo autorizado é **Etapa 8 — Mercado Livre Adapter**.
