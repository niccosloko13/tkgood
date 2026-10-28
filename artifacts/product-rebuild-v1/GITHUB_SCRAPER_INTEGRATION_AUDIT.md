# Etapa 12 — Auditoria dos três projetos GitHub

Data: 2026-10-28. Análise do README, licença e dependências publicados nos repositórios. **Não foi feita análise exaustiva de todo o código-fonte, execução de scrapers ou testes de acesso às plataformas.**

| Projeto | Licença | Evidências no repositório | Decisão |
|---|---|---|---|
| [omkarcloud/shopee-scraper](https://github.com/omkarcloud/shopee-scraper) | MIT | `requirements.txt`: bottle, cheroot, curl_cffi, marshmallow, pytest. README anuncia API local, dados de ofertas, produtos e tendências; também divulga RapidAPI. | Estudar esquema de campos e exemplos; **não executar scraping externo**. |
| [scraper-bank/Aliexpress.com-Scrapers](https://github.com/scraper-bank/Aliexpress.com-Scrapers) | MIT | Python e Node.js, JSONL; README recomenda chave ScrapeOps e técnicas de proxy/antibot. | Reaproveitar conceito de JSONL e parsers de arquivos; **não ativar automação/requisições**. |
| [BrenoFariasdaSilva/E-Commerces-WebScraper](https://github.com/BrenoFariasdaSilva/E-Commerces-WebScraper) | Apache-2.0 | Arquivos `AliExpress.py`, `Shopee.py`, `product_utils.py`; README informa HTML local, ZIP, processamento batch, Playwright, perfis Chrome autenticados e Gemini opcional. | Reaproveitar somente ideias de normalização e leitura offline; **não reutilizar perfis Chrome, cookies ou APIs pagas**. |

## Implementação concreta

- `app/market_radar/offline_import.py`: importador local independente. Modelos compatíveis com `MarketplaceProductObservation` e `NormalizedProduct`. Até 20 registros e até 2 MB por arquivo.
- `tests/test_market_radar_offline_import.py`: seis casos de teste escritos para leitura JSON/JSONL/CSV/HTML JSON-LD, limite de tamanho, deduplicação, categorias.
- **Nenhum código proprietário de terceiros foi copiado**; implementação original inspirada em formatos comuns, mantendo bibliotecas externas fora da árvore de dependências.
- Origem em `evidence.import_origin`: `FIXTURE` ou `IMPORTED_FILE`. `SourceType.THIRD_PARTY_PROVIDER` é uma classificação técnica provisória porque o enum vigente não possui `IMPORTED_FILE`; o campo de evidência determina a origem e a interface não deve promovê-lo a fonte oficial.
- Nunca preencher ranking, vendas ou visitas por inferência.
- Importador **não salva no Neon**, não cria endpoint e não tem acesso à rede. Persistência futura requer autorização, validação e separação física das coleções oficiais.

## Riscos e limitações

1. Licença open source não equivale a autorização do marketplace para coleta sistemática.
2. README não garante que o código funcione hoje nem que seja gratuito em escala.
3. HTML local aceita somente JSON-LD `Product`, não todos os tipos de página.
4. URLs comerciais são validadas por host; imagens ficam apenas como strings HTTPS, **não são requisitadas pelo importador**. Se uma UI futura as acessar, validar domínio/segurança e prevenir SSRF no backend.
5. Sem visita/venda em 48h comprovada, essas métricas seguem `null`.
6. Não houve implantação, extração de segredos ou alteração de OAuth.
