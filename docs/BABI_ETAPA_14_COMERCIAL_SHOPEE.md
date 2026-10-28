# Babi Etapa 14 — Inteligência Comercial Shopee Brasil

## Código implementado em branch

- Persistência isolada no Neon: `babi_commercial_metrics`; não altera rankings oficiais ML, OAuth ou TikTok.
- `scripts/collect_shopee_commercial.py` é o conector **opcional** da API Nexscope YouYing Shopee Product Search, estação BR. Exige `NEXSCOPE_API_KEY`, `OAUTH_DATABASE_URL`, autorização de uso da API, aceite comercial e saldo de créditos.
- `GET /api/v2/market-radar/commercial-ranking?marketplace=SHOPEE&metric=sold_30d` e métricas `estimated_sold_30d`, `historical_sold`, `views_total`, `revenue_30d`.
- UI exibe vendas de 30 dias reportadas, estimativas de fornecedor, acumulados e visualizações, cada um **com etiqueta correta**, data de observação e origem. Sem dados, vazio honesto.
- Exemplos GitHub são **fixtures**, não produtos reais, e não foram importados.

## Fontes

- https://github.com/nexscope-ai/nexscope-ecommerce-api/blob/main/docs/data/shopee-product-search.md
- https://github.com/nexscope-ai/nexscope-ecommerce-skills/blob/main/ecommerce-shopee-product-search/SKILL.md
- https://github.com/akira-kun/shopeev4api (GPL-3.0, exemplo antigo; não usado para acesso não autorizado nem contorno de bloqueios).

**Atenção:** A especificação de Nexscope documenta filtro de `sold` 30d e `historicalSold`. O payload vivo pode vir em envelope diferente do exemplo. A CLI recusa formas que não reconhecer e nunca finge sucesso.

## Ativação operacional

No ambiente protegido do operador autorizado, sem expor nem versionar segredos:
```powershell
python -m pytest tests/test_market_radar_commercial_metrics.py -q
python -m pytest -q
cd ui-v2
npm run check
npm run build
cd ..
python -m scripts.collect_shopee_commercial --limit 10 --dry-run
python -m scripts.collect_shopee_commercial --limit 10
```

Conferir valores, acesso e custo do provedor. O argumento `--dry-run` **consulta a API de terceiros**, portanto pode consumir créditos, embora não faça gravação no Neon.

Depois validar API e UI em preview, migrar tabelas via primeira escrita autorizada e só então liberar deploy de produção.

## 48 horas e crescimento

`sold_30d` não vira `sold_48h`. Para 48 horas, é necessário capturar contadores acumulados comparáveis do mesmo produto com 48h de diferença ou contratar uma fonte que forneça a janela diretamente. Até lá, dados 48h permanecem indisponíveis. `viewCount` é acumulado se a fonte não especificar período; não transformar em visualizações semanais.

## Estado desta execução

Arquivos de código e documentação adicionados à branch. Sem `NEXSCOPE_API_KEY` compartilhada e autorização específica do provedor, **nenhuma consulta real à Shopee, nenhum registro comercial e nenhuma migração ao Neon foram executados aqui**. Testes e build também pendem de execução em ambiente de CI/operador. **Não declarar funcionamento em produção por ter código no GitHub.**
