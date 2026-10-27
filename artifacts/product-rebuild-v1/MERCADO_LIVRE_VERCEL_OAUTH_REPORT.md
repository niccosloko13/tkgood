# Mercado Livre OAuth no Vercel

## Correção

O callback anterior completava a troca OAuth, mas tentava gravar tokens no
arquivo `.env`. O filesystem das Functions do Vercel é somente leitura, então
a autorização terminava com erro depois da troca de código.

## Armazenamento de produção

- Reutilizado: projeto Neon `radar`, banco `neondb`.
- Conexão: variável sensível `OAUTH_DATABASE_URL` (pooler).
- Chave: variável sensível `MERCADO_LIVRE_TOKEN_ENCRYPTION_KEY`.
- Algoritmo: AES-256-GCM com nonce aleatório de 96 bits e AAD por versão.
- Tokens, refresh tokens e PKCE verifiers são cifrados antes da persistência.
- Nenhum token é retornado por endpoints, logs, relatórios, SQLite ou frontend.

## Estado e refresh

`market_oauth_transactions` guarda hash de `state`, verifier cifrado, expiração
e consumo único. Isso permite que `/auth/start` e `/auth/callback` cheguem a
instâncias Vercel diferentes sem perder a validação PKCE.

`market_oauth_credentials` guarda o par de tokens cifrado. O refresh usa
`SELECT ... FOR UPDATE` e atualiza access/refresh token na mesma transação para
evitar reutilização concorrente do refresh token de uso único.

## Migração

As duas tabelas usam `CREATE TABLE IF NOT EXISTS`; a migração é idempotente e
não modifica as tabelas TikTok/SQLite. A criação foi validada no Neon e não há
credenciais Mercado Livre persistidas após a validação.

## Validação

- Testes direcionados: 25 aprovados (`api_v2`, Market Radar e OAuth store).
- UI V2: `npm run check` e `npm run build` aprovados.
- Banco Neon: migração criada e uma transação PKCE foi criada/consumida por
  conexões separadas, confirmando persistência entre execuções.
- Chave AES foi configurada somente como secret do Vercel; não foi adicionada
  a arquivos locais ou versionados.

## Proteção de endpoints

O deployment de produção permanece protegido por Vercel Authentication. Assim,
`auth/start`, `auth/refresh` e `collect` não são acessíveis anonimamente pela
internet. O callback OAuth não contém tokens e valida o `state` de uso único.

## Pendência obrigatória antes de nova autorização

O Client Secret enviado anteriormente em conversa deve ser rotacionado no
Mercado Livre DevCenter. Depois, configure somente o novo valor como secret
`MERCADO_LIVRE_CLIENT_SECRET` em Production no Vercel. Nenhuma nova autorização
OAuth foi iniciada por esta correção.
