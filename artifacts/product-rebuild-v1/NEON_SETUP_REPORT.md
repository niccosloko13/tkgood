# BABI — Etapa 12: Neon isolado para imports offline

Executado em 28/10/2026.

## Escopo preservado

- Nenhuma tabela de ranking oficial do Mercado Livre foi alterada.
- OAuth, TikTok, Safety e DiscoveryRunner não foram modificados.
- A conexão Neon foi usada por runtime/CLI autenticado, sem registrar a URL ou
  qualquer credencial em arquivos versionados, logs ou este relatório.

## Migração e verificação reais

As tabelas isoladas foram preparadas e verificadas no Neon já configurado:

- `market_radar_offline_imports`: criada e acessível.
- `market_radar_offline_import_products`: criada e acessível.
- Após a validação: `Batches=1`, `imported_products=2`.

Elas permanecem separadas de `market_radar_products` e
`market_radar_snapshots`.

## Importação autorizada de validação

Foi usado um arquivo fixture local de dois registros, marcado explicitamente
como `FIXTURE` e **não comercial/não ao vivo**. Não representa ranking, vendas,
visitas ou dados reais de marketplace.

- Marketplace: `SHOPEE`.
- Dry run: 2 registros válidos, sem escrita.
- Lote persistido: `c17655e5-6807-4708-af25-006ae82f98d9`.
- Registros persistidos: 2.
- Ranking oficial: `null` para ambos.
- Vendas e visitas: `null` para ambos.

## Leitura e interface

- API de produção validada:
  `GET /api/v2/market-radar/offline-imports/SHOPEE` retornou os 2 registros com
  `mode=OFFLINE_IMPORT`, `official_ranking=false` e `not_live=true`.
- Preview validado: build Ready e a mesma rota responde corretamente no estado
  vazio, pois Preview não recebe o segredo de banco de Production.
- A UI V2 identifica esses registros como produtos importados, não como ranking
  oficial ou coleta ao vivo.

## Proteção dos dados oficiais

As cinco categorias oficiais permaneceram legíveis e isoladas; total conferido:
93 posições (`20 + 20 + 13 + 20 + 20`).

## Validações

- Teste específico de importação offline: 6 aprovados.
- Suíte Python completa: 599 aprovados.
- `npm run check`: aprovado.
- `npm run build`: aprovado.
- Preview Vercel: Ready.
- Produção promovida somente após os testes completos aprovados.

## Observação de segurança

Uma string de conexão foi acidentalmente exposta a uma saída de ferramenta
durante o diagnóstico. A senha do role Neon foi rotacionada e
`OAUTH_DATABASE_URL` foi substituída como segredo de Production antes da
validação final. Nenhum valor sensível é registrado aqui.
