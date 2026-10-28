# Mercado Livre — integridade de rankings e auditoria comercial

Data: 28/10/2026 (UTC)

## Causa raiz

`market_radar_products` identifica um produto por `marketplace + external_id`.
Essa identidade é global e seu campo `source_category` era mutável. A leitura de
Top 20 filtrava esse campo do cadastro do produto, mas juntava todos os
snapshots. Após uma coleta posterior, a categoria mais recente do produto podia
substituir a categoria da observação anterior. Por isso um registro podia ser
exibido como `#1` em categorias nas quais nunca foi observado.

## Correção

- `market_radar_snapshots.source_category` é a fonte da categoria do ranking.
- A migração retropreenche o campo pela evidência `source_category_id`, sem
  remover snapshots existentes.
- A chave de unicidade passa a incluir categoria:
  `product_id + observed_at + source_category`.
- Top 20, categorias observadas e o enriquecimento limitado filtram a categoria
  do snapshot, não a categoria atual do produto.
- O cadastro do produto continua sendo identidade e metadados reutilizáveis;
  ele não define a posição oficial.

## Validação de produção — sem nova coleta

| Categoria oficial | Itens persistidos | #1 persistido | Categoria no snapshot | Tesoura `MLB26644010` |
| --- | ---: | --- | --- | --- |
| `MLB45425` — Campainhas | 20 | `MLB42998422` | `MLB45425` | ausente |
| `MLB268438` — Abridores de Latas | 20 | `MLBU3823641603` | `MLB268438` | ausente |
| `MLB272121` — Escovas Elétricas de Limpeza | 13 | `MLB57502851` | `MLB272121` | ausente |
| `MLB431814` — Cabos de Dados | 20 | `MLB44874479` | `MLB431814` | ausente |
| `MLB9522` — Carregadores para Câmeras | 20 | `MLB36185370` | `MLB9522` | ausente |

Todos os itens retornados para cada categoria têm `source_category` igual à
categoria solicitada. O histórico disponível começa em 28/10/2026; portanto,
uma janela de 48 h ainda está incompleta e não foi usada para inferir movimento.

## Auditoria comercial limitada (cinco registros)

Consultas oficiais autenticadas, somente leitura, sem pedidos e sem novos
snapshots. `NOT_APPLICABLE` significa que o identificador de catálogo não é um
anúncio comercial consultável pelo recurso de item.

| ID | Tipo | Detalhe | Preço/moeda | Imagem/link | Visitas | Unidades vendidas |
| --- | --- | --- | --- | --- | --- | --- |
| `MLB2735669440` | ITEM | HTTP 403 | HTTP 403 | restrito | HTTP 403 | não disponível |
| `MLB42998422` | PRODUCT | título disponível | não aplicável | imagem/link indisponíveis | não aplicável | não aplicável |
| `MLB44874479` | PRODUCT | título disponível | não aplicável | imagem/link indisponíveis | não aplicável | não aplicável |
| `MLBU3726445794` | USER_PRODUCT | HTTP 403 | não aplicável | restrito | não aplicável | não aplicável |
| `MLBU3823641603` | USER_PRODUCT | HTTP 403 | não aplicável | restrito | não aplicável | não aplicável |

Não houve tentativa de contornar respostas 403. Nenhuma consulta de pedidos foi
realizada. Mesmo quando `sold_quantity` estiver disponível futuramente para um
ITEM, ela deve ser apresentada como quantidade acumulada reportada pela fonte,
nunca como vendas em 48 horas. Visitas, unidades vendidas acumuladas e compras
confirmadas no período permanecem métricas distintas.

## Regressões e deploy

- Testes Python relevantes: 36 aprovados.
- `npm run check`: aprovado.
- `npm run build`: aprovado.
- Preview validado antes da promoção; produção implantada sem alterar TikTok,
  Safety, DiscoveryRunner, OAuth ou credenciais.
- Rollback permanece disponível por deployments anteriores do Vercel.
