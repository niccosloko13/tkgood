# Market Radar V2 — Etapa 10

## Entrega

Foi adicionada a página **Market Radar** à UI V2. Ela é uma camada de leitura: não inicia coletas, não aciona OAuth e não modifica snapshots, Mercado Livre, TikTok, Safety ou DiscoveryRunner.

## Experiência

- Cabeçalho com a data da última observação real e classificação da fonte.
- Seletor de fontes: Mercado Livre operacional quando houver autorização; AliExpress em preparação (adapter apenas de fixtures); Shopee, Alibaba e SHEIN com estado explícito.
- Ranking oficial do Mercado Livre limitado a 20 itens, em grade ou lista compacta.
- Filtros de categoria observada e período (`1d` a `90d`) usando somente os endpoints de leitura existentes.
- Cards mantêm posição oficial, preço, moeda, URL e imagem apenas quando a fonte os forneceu.
- Detalhes parciais e restritos são apresentados explicitamente. Não há dados sintéticos.
- Drawer de evidências com origem, data de observação, campos ausentes e histórico progressivo.
- Tendências de busca aparecem em seção separada e são identificadas como atualização semanal, não como ranking de vendas.
- Skeleton, erro, vazio e estados de fonte sem dados foram cobertos.

## Backend/read model

Novo endpoint de leitura: `GET /api/v2/market-radar/overview`.

Ele une fontes configuradas, categorias efetivamente observadas, Top 20 persistido, tendências persistidas e a última observação. Não expõe tokens ou detalhes de autenticação e não provoca nenhuma coleta.

Os endpoints existentes continuam compatíveis e são consumidos pela tela:

- `GET /api/v2/market-radar/mercado-livre/top`
- `GET /api/v2/market-radar/mercado-livre/trends`

`PostgresMarketStore.categories()` retorna somente categorias presentes nos snapshots reais; a UI não inventa nomes de categoria para IDs da fonte.

## Design e responsividade

O desenho reutiliza tipografia, cores, radius, sombras, drawer e navegação V2 existentes. Em desktop, os produtos usam grade de três colunas (duas em largura intermediária); no celular, passam para lista compacta, fontes viram uma faixa horizontal e filtros empilham sem reduzir o alvo de toque.

As escolhas de filtros enxutos e prioridade visual para o item principal seguem padrões contemporâneos de descoberta em e-commerce, sem reproduzir uma interface de terceiros. A revisão de referências destacou filtros baseados nos dados realmente disponíveis e padrões móveis de controles simples. [Shopify: filtros de e-commerce](https://www.shopify.com/blog/ecommerce-filters)

## Validação

- Python: `32 passed` — `tests/test_market_radar.py`, `tests/test_oauth_store.py`, `tests/test_api_v2.py`.
- TypeScript: `npm run check` aprovado.
- Testes da UI: `9 passed` — estados, idioma PT-BR, formatter, ranking/tendências e detalhes incompletos.
- Build: `npm run build` aprovado.
- Revisão React: hooks ficam no topo do componente, consultas independentes de filtro usam `Promise.all`, controles têm rótulos e `aria-pressed`, e não houve dependência adicional.

## Limitações reais

- Só Mercado Livre possui dados reais nesta página.
- Os preços/links de alguns registros são ausentes ou restritos pela própria fonte e continuam explicitamente parciais.
- O histórico não é apresentado como completo até que a janela solicitada seja coberta por snapshots reais.
- Não foi feito deploy nem coleta adicional nesta etapa.

## Arquivos principais

- `app/api_v2_market_radar.py`
- `app/market_radar/postgres_store.py`
- `ui-v2/src/main.tsx`
- `ui-v2/src/styles.css`
- `ui-v2/src/lib/api.ts`
- `ui-v2/src/lib/formatters.ts`
- `ui-v2/src/types.ts`
- `tests/test_api_v2.py`
- `ui-v2/tests/home-source.test.cjs`
