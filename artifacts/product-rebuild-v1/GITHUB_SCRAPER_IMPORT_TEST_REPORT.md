# Etapa 12 — Importador offline: relatório de implementação

Data: 2026-10-28

## O que foi efetivamente entregue

- Código novo `app/market_radar/offline_import.py` com leitura de arquivos locais JSON, JSONL, CSV e HTML/JSON-LD.
- Converte registros válidos de Shopee/AliExpress para modelos atuais da Market Radar Foundation, preservando `source_category`.
- Deduplicação exata por ID externo **dentro de cada importação**, limite de 20 linhas, arquivo de 2 MB, checagem de URL de produto HTTPS com host autorizado.
- Marca todo dado como importado ou fixture, com `rank=None`, `sales_count=None`, `views=None`, `order_count=None`, sem provar compras ou visitas.
- Não conecta bancos, não altera rank oficial Mercado Livre e não faz scraping.
- Seis testes unitários **adicionados**, ainda não executados neste ambiente.

## Estado de validação

- GitHub recebeu os arquivos e commits.
- Execução dos testes Python: **não realizada** aqui.
- TypeScript, UI tests e Vite build: **não executados** aqui.
- Fixture de 20 Shopee + 20 AliExpress: **ainda não executada**; há cobertura inicial com casos pequenos e entradas malformadas.
- Teste de ZIP, imagens e variantes: **ainda não implementado**. ZIP foi deliberadamente excluído da primeira versão para não introduzir risco de zip-slip/zip-bomb. Variantes precisam de modelo específico para não perder a distinção de preço.

## Próxima validação antes do merge

Executar no checkout local da branch:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_market_radar_offline_import.py -q
.\.venv\Scripts\python.exe -m pytest -q
cd ui
npm run check
npm run build
```
Ajustar o caminho da pasta UI de acordo com o monorepo real. Incluir fixtures locais de 20 itens por marketplace, testes de imagens, strings maliciosas e variantes. Revisar os diffs, as dependências e os avisos de licença antes de qualquer merge.

**Nenhuma coleta, deploy, alteração de dados ou bypass executado.**
