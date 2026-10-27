# Mercado Livre Adapter — Etapa 8

## Implementado

- Adapter oficial MLB, isolado em `app/market_radar/adapters/mercado_livre.py`.
- Autenticação por `MERCADO_LIVRE_ACCESS_TOKEN` somente em memória/cabeçalho.
- Best sellers oficiais por categoria via `/highlights/MLB/category/{CATEGORY_ID}`, com limite rígido de 20.
- Resolução separada para `ITEM` (`/items/bulk`), `PRODUCT` e `USER_PRODUCT`.
- Snapshots de ranking persistidos, incluindo resultados parciais quando o detalhe não é resolvido.
- Tendências semanais oficiais via `/trends/MLB[/CATEGORY_ID]`, persistidas separadamente de produtos.
- Histórico, movimento de ranking e Top 20 continuam explicáveis e baseados apenas nos snapshots Babi.
- Endpoints V2 de Top, Trends e coleta manual; o System V2 já consome o estado de fonte.

## Fonte e limites

`position` é o rank oficial. A fonte não fornece contagem de vendas, então nenhuma é inferida. O ranking não declara janela temporal: `source_window` fica ausente. Trends usam `source_window=weekly` e são keywords, não produtos.

Categorias folha são validadas pela API; `CATEGORY_NOT_RANKED` representa uma categoria sem ranking, sem afetar as outras fontes. O registry Babi não inventa IDs folha.

## Testes e integração real

Os testes usam transportes simulados oficiais para os fluxos normal, parcial, ITEM/PRODUCT/USER_PRODUCT, tendências 10/20/20, ausência de token, snapshots, movimento, histórico e limites. A integração externa é opcional e só pode rodar com `MERCADO_LIVRE_ACCESS_TOKEN`; não foi forçada sem essa configuração.

## Próximo passo

Validar uma categoria folha MLB com token provisionado e, somente depois, iniciar o adapter AliExpress. Nenhum marketplace adicional foi iniciado nesta etapa.
