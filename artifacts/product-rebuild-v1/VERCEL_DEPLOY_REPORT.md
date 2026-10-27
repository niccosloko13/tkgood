# Vercel deploy — Babi Product Rebuild V1

## Resultado

- Branch: `feat/babi-product-rebuild-v1`
- Commits publicados: `2c7dea1`, `a6f5aaf`, `e5192c9`, `84d9415`
- Projeto Vercel: `nexus-a534/babi-product-hunter`
- Framework/runtime: Vite como service `web` + FastAPI como service `api` (Python/Fluid Compute)
- Preview: `https://babi-product-hunter-libcjcpnd-nexus-a534.vercel.app` — READY
- Produção: `https://babi-product-hunter.vercel.app` — READY
- Deployment de produção: `dpl_BUxipZMWDAusD3WnSdUA8ooUUn2W`

## Validação

- Home estática: HTTP 200.
- Asset JavaScript principal: HTTP 200.
- `GET /api/v2/home`: HTTP 200, read model vazio esperado no ambiente novo.
- `GET /api/status`: HTTP 200.
- Scan de logs de runtime em produção, última hora: nenhum erro retornado.
- Preview e produção usam Deployment Protection; foram validados com o acesso autenticado da CLI, sem expor token de bypass.

## Configuração aplicada

O deploy usa dois Vercel Services e preserva caminhos de API:

- `/api` e `/api/*` são roteados ao FastAPI `app.main:app`.
- Demais rotas são roteadas à SPA Vite em `ui-v2`.
- `.vercelignore` exclui ambiente Python local, perfis Chrome, banco, artifacts, modelos e caches do bundle. Nenhum arquivo local foi apagado.

## Limitações importantes

O SQLite em Vercel usa `/tmp/babi`, portanto é efêmero por instância/deploy. A produção publicada valida a interface e APIs sem dados persistidos; não é apropriada para histórico de coleta, Browser Bridge ou operações TikTok. Esses fluxos continuam locais.

Não há variáveis de ambiente configuradas no projeto Vercel. Para OAuth Mercado Livre, configurar somente no painel Vercel:

- `MERCADO_LIVRE_CLIENT_ID`
- `MERCADO_LIVRE_CLIENT_SECRET`
- `MERCADO_LIVRE_REDIRECT_URI`

## Callback OAuth de produção

`https://babi-product-hunter.vercel.app/api/v2/market-radar/mercado-livre/auth/callback`

Essa URI não foi cadastrada automaticamente no DevCenter do Mercado Livre.
