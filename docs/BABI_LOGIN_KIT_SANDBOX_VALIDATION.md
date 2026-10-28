# Babi — validação Login Kit Sandbox (28/10/2026)

Status: domínio TikTok URL prefix foi verificado pelo operador. Sandbox do app BABI existe e Redirect URI foi informado no portal. **Ainda não foi realizado login OAuth real nem há confirmação de variáveis no Vercel.**

## Ambiente e segurança
Para testar credenciais Sandbox, usar um deployment isolado de Preview com variáveis Sandbox e redirect URI que corresponda EXATAMENTE ao cadastro do portal. O portal informado usa `https://babi-product-hunter.vercel.app/api/v2/tiktok-connect/callback` (domínio de produção); **não alterar credenciais de Production para Sandbox sem isolamento**, pois pode interromper usuários. Se for indispensável testar com domínio canônico, criar janela controlada com rollback explícito após testes e sem usuários ativos. Preferível cadastrar também um domínio Preview estável aprovado no portal.

No backend: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REDIRECT_URI`, `TIKTOK_OAUTH_ENCRYPTION_KEY` Fernet válido e `OAUTH_DATABASE_URL`. `TIKTOK_LOGIN_ENV=sandbox` apenas marca modo declarado no diagnóstico; **não alterna chaves automaticamente**.

## Diagnóstico sem revelar segredos
`GET /api/v2/tiktok-connect/setup-check`: booleanos para presença das chaves e validação da chave Fernet. `GET /api/v2/tiktok-connect/status`: status de conexão deste navegador. Não informar nem registrar segredos em capturas/vídeo.

## Fluxo de teste
1. Verificar Deploy Preview Ready e domínio/redirect URI iguais aos do portal.
2. Testar status e setup-check; não chamar `start` enquanto algum campo obrigatório estiver inválido.
3. Testar `/api/v2/tiktok-connect/start` apenas no navegador de teste; autorizar no TikTok com usuário de teste Sandbox.
4. Confirmar callback e `status.connected=true`; checar que não há senha/cookie TikTok no Neon.
5. Testar desconexão e estado expirado; conferir que a próxima consulta retorna não conectado.
6. Gravar vídeo MP4 do fluxo real, ocultando URL com parâmetros de code/state e qualquer token.
7. Só solicitar App Review após os Termos e a Privacidade estarem publicados, em URLs verificadas.

## Pendências
- O Client Secret de Production foi exposto anteriormente e precisa ser rotacionado antes do uso real.
- Login Kit conecta identidade/escopos oficiais, não a sessão de extensão Chrome nem coleção de contas de terceiros.
- Sem login sandbox executado ou testes CI neste ambiente. Não marcar a integração como aprovada/operacional.
