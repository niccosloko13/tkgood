# Babi — TikTok login oficial (Etapa 16)

## Implementado
O usuário pressiona **Continuar com TikTok** na tela Sistema. A Babi redireciona ao Login Kit oficial TikTok, com escopo mínimo `user.info.basic`. Não recebe senha, SMS, códigos 2FA ou cookies do TikTok. Callback valida `state` único e temporário associado ao navegador, troca `code` no servidor e salva tokens criptografados em tabela Neon separada, identificados por sessão de navegador. O botão Desconectar remove a conexão da Babi para este navegador, mas não equivale a revogação remota no TikTok.

## Variáveis no backend Vercel, nunca no frontend
- `TIKTOK_CLIENT_KEY` e `TIKTOK_CLIENT_SECRET`, criados na sua própria aplicação TikTok for Developers.
- `TIKTOK_REDIRECT_URI=https://babi-product-hunter.vercel.app/api/v2/tiktok-connect/callback` (registrar a URI idêntica na aplicação oficial).
- `TIKTOK_OAUTH_ENCRYPTION_KEY`: chave Fernet protegida (gerar com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`). Não compartilhar nem commitar.
- `OAUTH_DATABASE_URL`: Neon existente protegido.

Sem estas variáveis o botão fica indisponível. Não existe segredo público para usar sem app cadastrado. Evitar configurar num Preview com redirect de Production sem verificar os domínios e cookies.

## Celular: web x aplicativo
Para a Babi atual, que é uma web app/PWA, utilizar **Login Kit Web**, mesmo no celular. A autorização pode reutilizar login web existente, mas abrir diretamente o aplicativo TikTok com retorno garantido exige o SDK nativo iOS/Android e configuração de apps próprios. Não simular deep links ou assumir transferência da sessão entre TikTok app e browser.

**Importante: OAuth Login Kit NÃO cria sessão autenticada de navegador para o coletor.** Ele dá acesso apenas às APIs oficiais e escopos consentidos. Para coletar dados em páginas TikTok via extensão Chrome, cada usuário deve autorizar/login em navegador local sob seu controle, com sessão isolada local; não armazenar cookies, senhas ou perfis Chrome no Neon e não permitir múltiplos usuários compartilhando uma sessão.

## Segurança e limitações
- Login OAuth atual é vínculo básico por sessão browser, **não login completo de clientes na Babi**. Antes de abrir a Babi a usuários externos, criar autenticação/isolamento de clientes no painel e vincular conexões à identidade, não apenas ao cookie do navegador.
- Verificar rotação/refresh de token oficial e revogação pelo TikTok antes de uso prolongado; versão atual salva tokens mas ainda não implementa refresh automático.
- Há criptografia com Fernet em repouso; limitar acesso à chave e criar política de retenção.
- Revisar política de privacidade, consentimento e exclusão de dados antes de disponibilizar a terceiros.
- Não confundir uma autorização de `user.info.basic` com permissões de monitoramento generalizado ou automação de conta.

## Validação necessária
Testar callback inválido, estado expirado, escopos recusados, cookies SameSite=Lax, envio de tokens falhando, acesso de outro navegador, migração Neon e deploy controlado. Executar suíte Python e check/build de UI. Nenhuma conta foi conectada ou senha solicitada nesta execução.

## Documentação oficial
- https://developers.tiktok.com/docs/en/login-kit-overview
- https://developers.tiktok.com/docs/en/login-kit-web
- https://developers.tiktok.com/docs/en/oauth-user-access-token-management
