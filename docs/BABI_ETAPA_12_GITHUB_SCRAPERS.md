# BABI — ETAPA 12: Estudo e integração de ferramentas open source

**Projeto:** `niccosloko13/tkgood`  
**Branch:** `feat/babi-product-rebuild-v1`  
**Missão:** avaliar e reaproveitar ferramentas gratuitas do GitHub para a Market Radar Foundation, com importação rastreável de produtos e nenhuma dependência de API paga. Não presumir que código gratuito oferece acesso autorizado aos marketplaces.

## Repositórios obrigatórios

| Projeto | URL | Licença verificada | O que investigar |
|---|---|---|---|
| Shopee Scraper | https://github.com/omkarcloud/shopee-scraper | MIT | Modelos de produto, ofertas-relâmpago, tendências, avaliações e lojas; API local |
| AliExpress Scrapers | https://github.com/scraper-bank/Aliexpress.com-Scrapers | MIT | Parsers Python/Node, extração de produtos, formato JSONL |
| E-Commerces-WebScraper | https://github.com/BrenoFariasdaSilva/E-Commerces-WebScraper | Apache-2.0 | Estrutura multiloja, normalização, deduplicação, imagem, batch e arquivos locais |

**Achados preliminares nos READMEs:** omkarcloud anuncia execução local gratuita, mas também oferece RapidAPI; scraper-bank orienta usar chave ScrapeOps e divulga técnicas antibot; o projeto de Breno usa automação de navegador, inclusive perfis Chrome autenticados, e Gemini opcional. As afirmações dos READMEs não constituem validação de funcionamento nem autorização dos marketplaces.

## 1. Auditoria primeiro

Inspecionar código, licenças, requirements, README, testes e SHA do commit revisado de cada projeto. Determinar exatamente quais componentes funcionam sem assinatura, chave de serviço externo, conta, navegador de desktop ou gastos por chamada. Examinar dependências e riscos de executar código de terceiros. Manter avisos de licença e atribuições quando copiar/adaptar código.

Não instalar os três sistemas inteiros na Babi nem carregar código externo em ambiente com segredos do Neon, OAuth ou Vercel.

## 2. Implementação que queremos

Aproveitar componentes locais comprovados para criar na Babi um **pipeline de importação offline**, sem coleta automática nos marketplaces, capaz de ler amostras legitimamente obtidas em JSON, JSONL, CSV e HTML local.

Normalizar: marketplace; ID do produto e do anúncio; título; descrição; preço e moeda; preço promocional; URL; imagem; categoria; variante/SKU; avaliação; pedidos explicitamente exibidos; horário; proveniência; campo indisponível.

Regras:
- Preços por variante são distintos de preço único.
- Mesclar anúncios somente por identificadores confiáveis; similaridade de título gera candidatos para revisão.
- Snapshot deve manter sua categoria observada (`source_category`) e contexto de fonte.
- Importação/fixture **não** vira ranking oficial ou dado coletado ao vivo.
- Visitas, compradores únicos, vendas em 48 horas e conversão permanecem `null` quando a fonte não oferece os números verificados.
- Sanitizar HTML, arquivos, URLs e tamanhos; evitar scripts executáveis, SSRF e path traversal.
- Integrar-se à Market Radar Foundation, Neon e contratos V2 **sem alterar snapshots oficiais existentes**.
- Se não existir autenticação segura para upload administrativo, finalizar o pipeline de backend e testes sem expor upload público nem inventar novo login.

## 3. Aplicação por projeto

### Shopee — omkarcloud/shopee-scraper

Estudar modelos de produto, flash sale, preços, descontos, estoque, categorias, avaliações e trending. Usar fixtures locais para testar a normalização. Não habilitar scraping ao vivo ou acesso a endpoints internos sem autorização. Unidades vendidas anunciadas pelo projeto não equivalem necessariamente a compras confirmadas em 48 horas.

### AliExpress — scraper-bank/Aliexpress.com-Scrapers

Aproveitar somente parsers e formatos de saída offline compatíveis com a licença. **Não usar** ScrapeOps, proxies, técnicas de evasão, CAPTCHA bypass ou APIs internas. A auditoria prévia já identificou restrição de recuperação sistemática sem permissão escrita. Preservar `AliExpressAffiliateAdapter` como fixture-only até acesso oficial autorizado.

### Multiloja — BrenoFariasdaSilva/E-Commerces-WebScraper

Avaliar especialmente `product_utils.py`, `url_input_normalizer.py`, tratamento de imagem e suporte offline HTML/ZIP. Não importar perfis Chrome/cookies, automação de login, Gemini ou mecanismos de contorno de restrições. Conservar atribuições Apache-2.0 se reutilizar código.

### Mercado Livre

Preservar integração oficial, OAuth, refresh, categorias, Top 20, Neon, read model e correção de `source_category`. Jamais sobrescrever ranking oficial com arquivo importado.

## 4. Validação

Com fixtures e arquivos locais, testar até **20 produtos Shopee e 20 AliExpress**:
- Preços, moedas, imagens, links, SKU, variantes, dados ausentes.
- Deduplicação, isolamentos entre categorias e snapshots.
- JSON/JSONL quebrado, HTML com scripts, links maliciosos e arquivos grandes.
- Proveniência correta: `OFFICIAL_API` versus `IMPORTED_FILE` versus `FIXTURE`, adaptada ao contrato real.
- Nenhuma métrica comercial inventada.
- Testes Python, TypeScript check, UI tests e build.

Não fazer coleta real no AliExpress/Shopee, bypass, agendamento, deploy ou nova autorização nesta etapa.

## 5. Entregas

Criar:
1. `artifacts/product-rebuild-v1/GITHUB_SCRAPER_INTEGRATION_AUDIT.md` — commits auditados, dependências, licenças, funções úteis e riscos de cada repositório.
2. `artifacts/product-rebuild-v1/GITHUB_SCRAPER_IMPORT_TEST_REPORT.md` — teste offline com exemplos normalizados, cobertura, limitações e evidências.
3. Código e testes do importador offline **se** houver componentes adequados para integração; caso contrário, justificar sem fingir implementação.

Relatar: o que foi realmente incorporado de cada projeto, o que funciona gratuitamente, o que requer autorização, resultados de testes e arquivos alterados.

**Git:** continuar em `feat/babi-product-rebuild-v1`; commit e push apenas das mudanças validadas, sem segredos; não fazer merge em master nem deploy.

**Preservar:** TikTok, Safety, DiscoveryRunner, OAuth, credenciais, Neon e snapshots existentes.
