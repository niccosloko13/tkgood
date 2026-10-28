# Etapa 9 — AliExpress Adapter (planejamento)

## Estado desta proposta

O caminho **Public Research Adapter** foi avaliado na Etapa 9.2 e rejeitado:
os termos pÃºblicos do AliExpress proÃ­bem recuperaÃ§Ã£o sistemÃ¡tica de conteÃºdo
sem permissÃ£o escrita. Este plano Ã© reservado para uma futura integraÃ§Ã£o por
API oficial aprovada; ele nÃ£o autoriza scraping de pÃ¡ginas pÃºblicas.

## Objetivo

Adicionar uma fonte **AliExpress** ao Market Radar sem alterar o fluxo TikTok,
sem scraping HTML e sem misturar métricas de afiliado com vendas globais do
marketplace.

Este documento é um plano: nenhum adapter, credencial, coleta ou scheduler foi
criado nesta etapa.

## Decisão de integração a confirmar antes de implementar

O AliExpress expõe famílias de API diferentes, com contratos de autenticação e
de dados distintos:

1. **Affiliate API / Promotion Creatives** — apropriada para catálogo,
   produtos promovíveis, preço e links. A documentação oficial lista
   `aliexpress.affiliate.hotproduct.query`, `product.query` e
   `productdetail.get`. Chamadas são assinadas com App Key/App Secret no
   gateway Open Platform; não pressupor OAuth do Mercado Livre.
2. **Seller/Open Platform** — apropriada a dados de negócio de sellers
   autorizados, com OAuth 2.0 e políticas/whitelist próprias. Não deve ser
   usada para inferir mercado global sem autorização e escopo explícitos.
3. **Relatórios de pedidos Affiliate** — representam somente pedidos e
   conversões atribuídos ao afiliado. Não são um contador de vendas do
   AliExpress e ficam fora do Top 20 até esse significado ser confirmado.

O primeiro gate é criar/validar uma aplicação no Open Platform e confirmar por
escrito quais métodos foram aprovados para a conta. Nenhuma credencial deve ser
adicionada à Babi antes disso.

## Capacidades propostas

| Dado | Fonte possível | Regra de apresentação |
| --- | --- | --- |
| Produtos em destaque | `aliexpress.affiliate.hotproduct.query` | somente se a resposta declarar lista/posição; não chamar de mais vendido sem contrato explícito |
| Busca por produto/categoria | `aliexpress.affiliate.product.query` | registrar como resultado de catálogo/promoção |
| Nome, imagem, preço, URL | product query/detail oficial | persistir somente campos retornados |
| Volume disponível | campo oficial como `lastest_volume`, se aprovado | mostrar o nome da fonte; não converter em vendas globais |
| Pedidos | relatórios de afiliado, se autorizados | rotular como pedidos atribuídos ao afiliado, não como demanda do marketplace |
| Tendência/rank oficial | somente se método aprovado o declarar | caso contrário, indisponível |

## Autenticação e segurança

- Affiliate: guardar App Key/App Secret apenas em variáveis protegidas do
  ambiente; assinatura HMAC conforme protocolo oficial. Não expor assinatura,
  chave ou parâmetros secretos no frontend/logs.
- Seller: se a modalidade aprovada exigir OAuth, reutilizar os princípios do
  armazenamento cifrado e state/PKCE somente quando o contrato oficial daquele
  app confirmar que se aplicam.
- Não reutilizar credenciais, tokens ou tabelas OAuth do Mercado Livre para o
  AliExpress.
- Endpoints de iniciar credencial, sincronizar pedidos ou coletar dados devem
  permanecer operacionais/protegidos.

## Modelo de dados e snapshots

Reutilizar a foundation existente apenas depois de confirmar a compatibilidade:

- identidade: `ALIEXPRESS + external_id`;
- observação: preço, moeda, imagem, URL, categoria original, tipo/fonte,
  contexto da chamada e campos de volume retornados;
- `source_window`: `null` quando a fonte não declara período;
- `observation_window`: somente snapshots acumulados pela Babi;
- pedidos/commission de afiliado, se existentes, em uma estrutura separada dos
  produtos de catálogo;
- nenhuma agregação AliExpress × Mercado Livre nesta etapa.

## Períodos e limites

- Filtros da Babi (1d, 3d, 7d, 15d, 30d, 60d, 90d) representam apenas o
  histórico de snapshots da Babi.
- Não preencher período histórico anterior à primeira observação.
- Não codificar rate limit: obter o limite aprovado no console/documentação da
  aplicação, registrar respostas 429 e aplicar recuo limitado conforme o
  contrato oficial.
- Primeiro teste real: uma categoria ou uma busca, máximo 20 itens, sem cron.

## Sequência da Etapa 9

1. Confirmar modalidade (Affiliate ou Seller), aprovação e métodos permitidos.
2. Registrar apenas as variáveis necessárias no Vercel/local seguro.
3. Implementar cliente assinado e fixtures sem rede.
4. Mapear resposta oficial para `MarketplaceProductObservation`, mantendo
   dados parciais.
5. Criar coleta manual limitada e testes de assinatura, timeout, 401/403/429,
   resposta parcial e dedupe por `ALIEXPRESS + external_id`.
6. Validar uma execução real pequena, snapshots e histórico antes de qualquer
   UI ampla ou scheduler.

## Limitações conhecidas

- A documentação pública lista métodos de afiliado, mas disponibilidade e
  quotas dependem de aprovação da aplicação; isso precisa ser validado antes de
  prometer ranking ou pedidos.
- `hotproduct` não deve ser apresentado como ranking de vendas sem evidência
  oficial da semântica do campo/ordem.
- Não haverá scraping, navegador automatizado, marketplace cross-match, score
  novo nem coleta automática nesta etapa de planejamento.

## Fontes oficiais

- [AliExpress Open Platform — cadastro e aprovação](https://developer.alibaba.com/docs/doc.htm?articleId=120673&docType=1&treeId=727)
- [AliExpress Open Platform — processo e assinatura de chamadas](https://developer.alibaba.com/docs/doc.htm?articleId=120688&docType=1&treeId=727)
- [Affiliate product query — parâmetros e campos de resposta](https://developer.alibaba.com/docs/api.htm?apiId=45803)
- [Seller authorization — políticas OAuth e whitelist](https://developer.alibaba.com/docs/doc.htm?articleId=120677&docType=1&source=search&treeId=727)
