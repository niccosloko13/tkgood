# AliExpress Public Research Adapter — Etapa 9.2

Data: 2026-10-28

## Decisão

**NÃO IMPLEMENTADO.** Não foi encontrada uma fonte pÃºblica adequada cuja
coleta automatizada seja explicitamente permitida para este caso de uso.

O objetivo exigia ranking/catÃ¡logo pÃºblico observacional sem conta de
desenvolvedor. A fonte natural seria o site pÃºblico AliExpress, mas os termos
atuais proÃ­bem recuperaÃ§Ã£o sistemÃ¡tica de conteÃºdo para compilar coleÃ§Ãµes,
bancos de dados ou diretÃ³rios por robots, spiders, dispositivos automÃ¡ticos ou
processos manuais sem permissÃ£o escrita. A consulta a `robots.txt` tambÃ©m nÃ£o
pÃ´de ser confirmada pela ferramenta de pesquisa; isso nÃ£o substitui a
autorizaÃ§Ã£o expressa exigida pelos termos.

Portanto, criar `AliExpressPublicAdapter`, fazer requisiÃ§Ãµes limitadas ou usar
pacing nÃ£o tornaria a coleta permitida. Nenhuma chamada de coleta foi feita.

## Fontes auditadas

| Fonte | Natureza | Dados possÃ­veis | DecisÃ£o |
| --- | --- | --- | --- |
| PÃ¡ginas pÃºblicas AliExpress | catÃ¡logo/busca/listas variÃ¡veis | produtos, preÃ§os e possÃ­veis sinais de popularidade | rejeitada para coleta automatizada pelos termos |
| AliExpress Open Platform / Affiliate API | API oficial com App Key/App Secret e aprovaÃ§Ã£o | catÃ¡logo, hot products, detalhes e campos declarados pela API | fora do escopo “sem conta”; candidata Ã  Etapa 9 com credenciais aprovadas |
| Seller/Open Platform | API oficial com OAuth/autorizaÃ§Ã£o de seller | dados de sellers autorizados | fora do escopo; nÃ£o representa ranking pÃºblico geral por si sÃ³ |

Nenhum resultado comum de busca, publicidade ou lista editorial foi tratado
como "Top 20 mais vendidos".

## O que nÃ£o foi feito

- nenhum adapter, endpoint API V2 ou migration AliExpress;
- nenhuma coleta, scraping HTML, endpoint interno, login ou credencial;
- nenhum retry, proxy, stealth, CAPTCHA bypass ou tentativa de contorno;
- nenhuma alteraÃ§Ã£o em TikTok, Safety, DiscoveryRunner, Trend Engine, Mercado
  Livre, OAuth do Mercado Livre ou Neon.

## Caminho aprovado para a prÃ³xima etapa

Prosseguir somente via API oficial aprovada do AliExpress. O planejamento em
`docs/ALIEXPRESS_ADAPTER_PLAN.md` separa Affiliate (assinatura App Key/App
Secret) de Seller/Open Platform (OAuth), preserva provenance e proÃ­be inferir
vendas globais a partir de dados de afiliado.

Antes de qualquer adapter real, confirmar: modalidade da conta, aprovaÃ§Ã£o dos
mÃ©todos, quotas, semÃ¢ntica de `hotproduct`, limites de uso e campos permitidos.

## Testes e build

Como nenhuma implementaÃ§Ã£o de coleta foi autorizada, nÃ£o foram criadas fixtures
de pÃ¡gina nem testes de parser. A regressÃ£o existente e o build da UI foram
executados para confirmar que o bloqueio de escopo nÃ£o introduziu regressÃ£o.

## ReferÃªncias

- AliExpress Terms of Use, restriÃ§Ã£o de recuperaÃ§Ã£o sistemÃ¡tica: 
  <https://terms.alicdn.com/legal-agreement/terms/suit_bu1_aliexpress/suit_bu1_aliexpress202204182115_66077.html>
- AliExpress Open Platform, cadastro/aprovaÃ§Ã£o: 
  <https://developer.alibaba.com/docs/doc.htm?articleId=120673&docType=1&treeId=727>
- Affiliate Product Query: <https://developer.alibaba.com/docs/api.htm?apiId=45803>
- Seller authorization: 
  <https://developer.alibaba.com/docs/doc.htm?articleId=120677&docType=1&source=search&treeId=727>
