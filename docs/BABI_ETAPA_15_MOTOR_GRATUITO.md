# Babi — motor gratuito de crescimento comercial (Etapa 15)

## Visão
Não comprar Nexscope nem depender de endpoints privados. Usar ranking oficial Mercado Livre já autorizado e observações públicas **efetivamente visíveis** de contadores acumulados para acompanhar crescimento. O código é nosso. Dados dependem de fonte real, permissão de acesso e histórico.

## Implementado
- `app/market_radar/first_party_engine.py`: validador de até 100 observações JSON/JSONL, com domínio HTTPS autorizado, timestamp com fuso, número inteiro acumulado não negativo, IDs, link e origem obrigatórios.
- `scripts/import_public_sales_counters.py`: `--dry-run` e gravação isolada em `babi_commercial_metrics` no Neon já existente, sem mexer no Mercado Livre nem no TikTok.
- Reaproveita `GET /api/v2/market-radar/commercial-ranking` para `historical_sold` e `views_total`; `GET /api/v2/market-radar/commercial-growth` para diferenças entre snapshots em 48h/7d/30d.
- UI Market Radar exibe crescimento e período realmente amostrado; se faltam duas observações mostra estado vazio.
- Testes foram escritos, mas **não executados neste ambiente**.

## Exemplo de formato — apenas exemplo, NÃO dados reais
```json
[
  {
    "marketplace": "SHOPEE",
    "product_id": "SHOPID-ITEMID",
    "title": "Nome exibido na página",
    "product_url": "https://shopee.com.br/pagina-do-produto",
    "observed_at": "2026-10-28T15:30:00-03:00",
    "metric_name": "historical_sold",
    "metric_value": 1200,
    "category": "Casa"
  }
]
```
O operador só deve preencher `metric_value` com valor REAL mostrado pela fonte, preservando o comprovante externo conforme suas obrigações de auditoria. Nunca inferir de ranking, reviews, seguidores, faixa "1k+" ou `sold` comercial estimado.

## Uso no PC do operador
```powershell
python -m pytest tests/test_market_radar_first_party_engine.py tests/test_market_radar_commercial_metrics.py tests/test_market_radar_rank_momentum.py -q
python -m pytest -q
cd ui-v2; npm run check; npm run build; cd ..
python -m scripts.import_public_sales_counters --file C:\\dados\\observacoes.json --source-id shopee_public --dry-run
python -m scripts.import_public_sales_counters --file C:\\dados\\observacoes.json --source-id shopee_public
```
`OAUTH_DATABASE_URL` no ambiente protegido do operador; não copiar chave Neon para frontend nem logs.

## Limites honestos
- Ainda **não é um robô que varre a Shopee**. A importação é manual de arquivo validado. GitHub de um scraper não significa autorização ou garantia de campo disponível.
- Site Shopee pode ocultar números exatos; nesses casos importação de volume exato deve ser recusada até existir fonte efetiva.
- Exatamente 48h de vendas depende de fonte com esse período ou de duas observações de contadores equivalentes nesse intervalo. O motor mostra `sampled_hours` e não faz afirmação de medição exata.
- Não importa `fixture` como produto real; histórico do Mercado Livre usa rankings, não volume.
- Para monitoramento automático futuro: agendar coleta por fontes oficiais com campos disponíveis, com observabilidade, consentimento e limites de acesso.

## Estado operacional
Implementado na branch `feat/babi-product-rebuild-v1`. **Nenhum número real novo foi coletado, nenhum snapshot comercial foi persistido aqui, nenhum teste ou deploy de produção foi confirmado nesta sessão.** Antes do deploy: CI e testes completos, primeiro lote real, auditoria da procedência e revisão das telas.
