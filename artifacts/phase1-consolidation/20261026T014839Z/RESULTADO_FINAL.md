# Resultado — consolidação Babi v1, Parte 1

Checkpoint pré-alterações: `source-before.zip`, cópia do banco e `checkpoint.json` nesta pasta.

## Arquitetura

- `app.discovery_runner.DiscoveryRunner` centraliza planejamento limitado, fila, autorização, avanço, captura/persistência, finalização e relatório canônico.
- Stage 1 e Stage 2 usam os mesmos estados e lifecycle; seus limites vêm de `config/discovery_contract.json`. Os relatórios legados mantêm seus campos por compatibilidade e incorporam `discovery_run`.
- `app.safety` e `extension/safety_gate.js` implementam o contrato definido em `config/safety_contract.json`. São adaptadores puros dos sinais existentes e não fazem detecção de DOM, navegação, liberação de latch nem scoring.
- Search-only permanece limitado a resultados visíveis, sem scroll, com limites por stage e admissão Safety fail-closed.

## Alterações

Novos arquivos:

- `app/discovery_runner.py`, `app/safety.py`
- `extension/safety_gate.js`
- `config/discovery_contract.json`, `config/safety_contract.json`
- `tests/test_discovery_runner.py`, `tests/safety-contract.test.cjs`
- `docs/DISCOVERY_RUNNER.md`, `docs/SAFETY_CONTRACT.md`, `docs/ARTIFACT_RETENTION.md`
- `artifacts/current/README.md`, `artifacts/archive/README.md`

Arquivos integrados ou adaptados:

- `app/db.py`, `app/safe_collection.py`, `app/safe_collection_api.py`, `app/browser_safety.py`, `app/target_safety.py`
- `extension/background.js`, `extension/manifest.json`, `extension/search_stability.js`
- `scripts/quarantine_stage1.py`, `scripts/controlled_stage2.py`, `scripts/resume_stage2.py`
- `tests/safe-collection.test.cjs`, `tests/search-stability.test.cjs`

## Depreciação e compatibilidade

As funções de lifecycle antigo em `app.safe_collection` são adaptadores deprecated para `DiscoveryRunner`. Os CLIs `quarantine_stage1.py`, `controlled_stage2.py` e `resume_stage2.py` também estão marcados deprecated e continuam como adapters de operador para manter comandos, checkpoints e relatórios antigos. Nenhum desses arquivos foi removido.

## Limpeza e retenção

- Removidos pelo menos 134 arquivos regeneráveis dos diretórios SAFE: `.pytest_cache`, `__pycache__`, `app/__pycache__`, `scripts/__pycache__`, `tests/__pycache__`.
- Espaço medido na limpeza principal: 1.412.436 bytes (aprox. 1,35 MiB). Um cache Python pequeno foi regenerado pelo diagnóstico final e removido em seguida; esse acréscimo não foi medido, então o total recuperado é ligeiramente maior.
- Nenhum outro arquivo foi apagado ou movido. Os perfis de teste `.runtime/dashboard-ui-test-*` permanecem preservados (classificação probably safe, não SAFE).
- Os 14 checkpoints SQLite (~65,8 MiB) e a árvore `artifacts/` permanecem intactos; a retenção foi documentada sem arquivamento automático.

## Testes e regressões

- Python final: **537 passed, 7 warnings**, exit code 0.
- JavaScript: **173 passed, 0 failed**, exit code 0.
- Testes focados de DiscoveryRunner, Stage 1/2 e retomada: **36 passed**.
- Durante a primeira repetição completa foi encontrado um erro de configuração no teste novo (fixture `library` não importada). A importação foi corrigida; a execução final completa passou.
- Os 7 avisos são de APIs deprecated do FastAPI/websockets e bindings SWIG; não são falhas desta mudança.
- Regressões funcionais restantes: nenhuma identificada pelas suítes executadas.

## Integridade e estado de operação

- Os 66 arquivos protegidos cobertos pelo checkpoint mantêm os hashes originais.
- Banco `data/product_hunter.db`: mesmo tamanho de 8.572.928 bytes; 85 tabelas; nenhuma contagem divergente. `search_observations=203`, `trend_snapshots=428`, `videos=53`.
- `extension.pem` mantém o hash do checkpoint. `browser-profiles/chrome-tiktok-main` continua presente.
- Nenhum latch foi liberado. Estado persistido continua com global security stop por challenge, `DIRECT_VIDEO_ENRICHMENT=PAUSED` e guard de coleta habilitado.
- `devctl status`: backend offline, Companion/aba TikTok não reconhecidos; porta 8000 sem listener. Não foi feita coleta ao vivo, pois isso exigiria estado saudável e o stop atual deve ser preservado.

## Limites e pendências para Parte 2

- Fazer health check manual/passivo e liberar o latch somente pelo fluxo de recuperação já existente antes de qualquer coleta ao vivo. Search-only está disponível condicionalmente quando Safety permitir; agora está bloqueado pelo latch persistente.
- Revisar externamente os consumidores dos adapters deprecated antes de removê-los ou alterar relatórios históricos.
- Os perfis isolados de teste foram verificados sem processo Chrome apontando para eles, mas não apagados por serem probably safe e exigirem aprovação/revisão separada.
- Nenhuma dependência pesada foi removida ou separada; isso permanece para uma fase com prova de instalação independente.
- Nenhum código suspeito/experimento foi movido para `tools/legacy`; a compatibilidade e o uso manual precisam de revisão dedicada antes de qualquer movimento.
- Stage 3, Trend Engine v2, enrichment e qualquer coleta nova continuam fora desta fase.
