# BABI — Etapa 12: ativação segura do Neon e interface dos imports

**Status em 28/10/2026:** implementação preparada na branch `feat/babi-product-rebuild-v1`, sem acesso operacional confirmado ao Neon neste ambiente. **Nenhum dado real foi gravado e nenhum deploy de produção foi feito nesta execução.**

## O que já existe

- O Market Radar oficial já usa Neon por meio da variável protegida `OAUTH_DATABASE_URL` em `hosted_market_store()`. **Não criar outro banco nem nova connection string.**
- Importação offline Shopee/AliExpress: `app/market_radar/offline_import.py`.
- Persistência exclusiva de importações: `app/market_radar/offline_store.py`.
- Leitura na API V2: `GET /api/v2/market-radar/offline-imports/{SHOPEE|ALIEXPRESS}`.
- Exibição no Market Radar V2: produtos de arquivo identificados como **não oficiais e não coletados ao vivo**.
- Importação operacional via CLI, não via endpoint público: `scripts/import_marketplace_offline.py`.
- Preparação e verificação da estrutura de tabelas isoladas: `scripts/prepare_market_radar_neon_imports.py`.

## O que foi alterado nesta rodada

- Corrigida falha de consistência: rejeitar lote vazio, lotes com marketplaces misturados e observações contendo posição de ranking.
- Unificada a variável de conexão da CLI com o backend hospedado: apenas `OAUTH_DATABASE_URL` (não usar outro banco acidentalmente).
- Adicionado comando explícito de migração e verificação.
- Não criar tabelas de ranking novas, não migrar nem modificar `market_radar_products` ou `market_radar_snapshots`.

## Passos de execução para um operador autorizado

1. Confirmar que o deployment de destino já usa `OAUTH_DATABASE_URL` em produção. Verificar apenas presença da variável; **não mostrar, copiar para chat nem versionar o valor**.
2. Num ambiente autorizado que tenha acesso à mesma variável e a permissões DDL no Neon, na raiz do repositório:
   ```powershell
   python -m scripts.prepare_market_radar_neon_imports --migrate
   python -m scripts.prepare_market_radar_neon_imports --verify
   ```
3. Criar localmente um arquivo de produtos legitimamente obtido (JSON, JSONL, CSV ou HTML local), com até 20 produtos e no máximo 2 MB. Não incluir dados pessoais, cookies, segredos nem páginas obtidas por métodos proibidos.
4. Simular a leitura sem tocar no banco:
   ```powershell
   python -m scripts.import_marketplace_offline --marketplace shopee --file C:\\dados\\produtos.json --dry-run
   ```
5. Importar **apenas** um arquivo validado e aprovado:
   ```powershell
   python -m scripts.import_marketplace_offline --marketplace shopee --file C:\\dados\\produtos.json
   ```
6. Confirmar `--verify` e consultar `GET /api/v2/market-radar/offline-imports/SHOPEE` no deployment atualizado. Conferir que os produtos aparecem como importados e que o Mercado Livre mantém exatamente suas 93 posições oficiais anteriores.

## Segurança e verdade dos dados

O processo de importação **não faz scraping**, não é um conector ativo e não autoriza coletar sistematicamente Shopee/AliExpress. Ter o código no GitHub não fornece visitas ou vendas precisas. Ranking, vendas em 48 horas e visitas permanecem indisponíveis quando não fornecidos oficialmente.

As tabelas `market_radar_offline_imports` e `market_radar_offline_import_products` são separadas das tabelas oficiais. **Não misturar** resultados importados com rankings do Mercado Livre.

O comando de importação roda somente no terminal autorizado; não há upload público na interface. A API de leitura não contém segredos, mas uma revisão de controles de acesso e privacidade é necessária se arquivos futuros contiverem dados não públicos.

## Testes antes de produção

```powershell
python -m pytest tests/test_market_radar_offline_import.py -q
python -m pytest -q
cd ui-v2
npm run check
npm run build
```

O ambiente desta conversa não conseguiu executar esses comandos. **Resultados pendentes.** A migração DDL e gravação no Neon também ainda não foram executadas.

## Pendências reais

- Executar testes CI/local e corrigir qualquer falha.
- Executar `--migrate`/`--verify` em ambiente autorizado com `OAUTH_DATABASE_URL`.
- Validar leitura e gravação de um arquivo legítimo pequeno.
- Validar Preview antes de promover a interface.
- Revisar comportamento de importações múltiplas, variantes, sanitização de imagens e UX antes de afirmar solução completa.

Não há necessidade de criar outra conta Neon, adicionar nova API paga ou rotacionar o OAuth do Mercado Livre.
