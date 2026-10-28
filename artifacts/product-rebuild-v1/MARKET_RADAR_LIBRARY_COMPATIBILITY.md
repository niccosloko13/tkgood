# Market Radar — Compatibilidade de bibliotecas abertas

Data: 2026-10-28

## Escopo e decisÃ£o

Foram revisadas bibliotecas indicadas para preparar integraÃ§Ãµes oficiais. Nenhuma
dependÃªncia de terceiros foi adicionada ao projeto e nenhum dado real foi
coletado. A Babi continua distinguindo: biblioteca disponÃ­vel, credencial
necessÃ¡ria, permissÃ£o concedida, fixture de teste e dado real persistido.

## AliExpress

### `sergioteula/python-aliexpress-api`

- LicenÃ§a: MIT, confirmada no arquivo `LICENSE` do repositÃ³rio.
- Pacote declarado: versÃ£o 3.1.0, Python >=3.6, sem dependÃªncias externas
  declaradas alÃ©m de setuptools.
- MÃ©todos revisados: `get_products`, `get_hotproducts`,
  `get_products_details`, `get_categories`, `get_parent_categories` e
  `get_child_categories`.
- Contrato: wrapper para Affiliate API/Open Platform com App Key, App Secret e
  parÃ¢metros de afiliado; nÃ£o habilita acesso sem aprovaÃ§Ã£o de API.

Foi criado `AliExpressAffiliateAdapter` interno, sem instalar ou copiar a
biblioteca. Ele aceita apenas um transport injetado e normaliza fixtures com o
envelope oficial Affiliate. Por padrÃ£o nÃ£o possui transport/credencial,
permanece `available=false` e nÃ£o faz rede.

`get_hotproducts` Ã© apresentado como lista de produtos populares da Affiliate
API, nÃ£o como Top 20 de vendas: a observaÃ§Ã£o recebe `rank=null`,
`ranking_available=false` e `sales_count=null` enquanto a semÃ¢ntica oficial de
ranking/venda nÃ£o for aprovada.

## Shopee

| Biblioteca | LicenÃ§a observada | Contrato | Descoberta geral/ranking |
| --- | --- | --- | --- |
| `GabMalta/shopee-sdk` | MIT | Shopee Open Platform v2, HMAC + OAuth por shop/merchant | nÃ£o demonstrado; opera recursos de loja autorizada |
| `trungdangtapcode/shopee-open-platform-mock` | nenhuma licenÃ§a raiz identificada na revisÃ£o | mock local/SDK de schemas | somente teste; nunca dado real |
| `jeividev/shopee` | MIT | Shopee Affiliate API para shortlink | nÃ£o demonstra ranking, vendas ou tendÃªncias gerais |

ConclusÃ£o: nenhuma das trÃªs Ã© base suficiente para declarar ranking geral de
produtos Shopee. O SDK de Open Platform pode ser considerado no futuro para
dados da prÃ³pria loja autorizada, mantendo-os separados de qualquer Market
Radar de marketplace. O mock nÃ£o deve ser conectado a persistÃªncia real.

## Cobertura de testes

Fixtures locais cobrem:

- normalizaÃ§Ã£o de hot-product Affiliate com nome, imagem, preÃ§o, moeda e URL;
- omissÃ£o de produto invÃ¡lido/parcial;
- limite mÃ¡ximo de 20;
- ausÃªncia de rank e de vendas inferidas;
- adapter indisponÃ­vel sem transport oficial.

NÃ£o foram simulados pedidos ou vendas como dados de mercado. O adapter nÃ£o foi
registrado como fonte disponÃ­vel para coleta, nÃ£o expÃµe endpoint V2 e nÃ£o cria
snapshots fora dos testes.

## ValidaÃ§Ã£o

- Testes Python relevantes: 30 aprovados.
- `npm run check`: aprovado.
- `npm run build`: aprovado.
- Nenhuma coleta, credencial, scheduler ou deploy foi executado.

## ReferÃªncias

- [python-aliexpress-api](https://github.com/sergioteula/python-aliexpress-api)
- [Shopee SDK](https://github.com/GabMalta/shopee-sdk)
- [Shopee Open Platform mock](https://github.com/trungdangtapcode/shopee-open-platform-mock)
- [Shopee affiliate wrapper](https://github.com/jeividev/shopee)
- [AliExpress Affiliate Product Query oficial](https://developer.alibaba.com/docs/api.htm?apiId=45803)
