# BABI — Etapa 13: TikTok local → Neon → Vercel

**Estado:** implementação inicial enviada na branch `feat/babi-product-rebuild-v1`; **não implantada, não ativada e não verificada com Neon real nesta execução**.

## Arquitetura implementada

1. **Coletor local:** mantém Chrome, extensão, DiscoveryRunner, SQLite e todas as regras de segurança existentes.
2. **Script manual local:** `python -m scripts.sync_tiktok_library_to_neon --dry-run` consulta somente o read model da biblioteca local. O envio real é `python -m scripts.sync_tiktok_library_to_neon`.
3. **API Vercel:** `POST /api/v2/tiktok-sync/videos` recebe lotes de 1–100 vídeos, apenas com header secreto `X-Babi-Tiktok-Sync`. Não aceita browser cookies, HTML, eventos de missão, comando de curtir etc.
4. **Neon:** `babi_tiktok_library_mirror` (tabela separada; upsert por video_id).
5. **Interface:** biblioteca V2 pode ler o Neon após ativar `BABI_TIKTOK_NEON_READS=1` no Vercel, inclusive endpoint de detalhe; `GET /api/v2/tiktok-sync/status` informa contagem/última sincronização.

## Ativação segura — operador local

- **Não criar banco novo:** usar `OAUTH_DATABASE_URL` existente **apenas no servidor Vercel**. Não copiar connection string para o navegador ou para o ChatGPT.
- Criar um segredo aleatório com no mínimo 32 caracteres (idealmente 32 bytes aleatórios codificados em hexadecimal). Cadastrar no Vercel como `BABI_TIKTOK_SYNC_TOKEN`, no ambiente que vai receber a sincronização.
- Configurar localmente `BABI_TIKTOK_SYNC_TOKEN` com o mesmo valor e `BABI_TIKTOK_SYNC_URL=https://babi-product-hunter.vercel.app`. **Não salvar segredo em Git.**
- Manter `BABI_TIKTOK_NEON_READS` **desativado** até completar a primeira sincronização e comparar a contagem local com a remota.
- Executar `--dry-run` localmente, conferir total; após Preview validado e deploy controlado do endpoint, executar sincronização manual.
- Confirmar `GET /api/v2/tiktok-sync/status` com `count` e `last_synced_at` e, em seguida, testar `GET /api/v2/library` no Preview com flag ativa. Testar vazio, ordenação, filtros, detalhe e refresh.
- Se os valores estiverem corretos, ativar a flag no deployment de produção e validar contagens. A flag pode ser desligada para retornar temporariamente ao leitor antigo.
- **Atenção:** sem agendamento, a sincronização não é em tempo real. A CLI atual envia até 2000 vídeos por execução (ajustável por `--limit`, máximo 10000); se houver mais dados, executar com critério adequado antes de promover.
- Como a Vercel é stateless, **não acionar DiscoveryRunner/browser pela função serverless** como se ele estivesse conectado ao Chrome local. Os endpoints de missão ainda não são uma fila remota operacional.

## O que esta etapa NÃO migrou ainda

A migração completa do SQLite para Postgres **não foi feita**. Persistência local de comentários, criadores, tarefas/filas, evidência detalhada, candidatos e trend engine permanece em SQLite. O mirror atual replica apenas os campos da biblioteca. Home, Discovery, Oportunidades e Sistema ainda precisam de read models Neon e filas/worker autenticados para funcionar como um dashboard remoto completo.

## Privacidade e segurança

O script exporta dados de apresentação da biblioteca, não o arquivo SQLite. Não sincroniza cookies, credenciais, perfil Chrome, HTML bruto ou dados de sessão. O segredo é obrigatório para POST inclusive no desenvolvimento, e deve ser rotacionado se exposto. URLs e metadados de vídeos podem conter dados de criadores, portanto restringir ao uso autorizado e revisar retenção e controles de acesso antes de abrir para visitantes.

## Comandos de validação

```powershell
python -m pytest tests/test_tiktok_neon_mirror.py -q
python -m pytest -q
cd ui-v2
npm run check
npm run build
```

**Nesta execução os comandos acima não foram executados. Nenhuma credencial, migração real ou deploy foi realizado.**

## Critérios para próxima etapa

- CI e testes locais passam.
- Envio autenticado ao Preview/produção com lote pequeno.
- Contagem e IDs conferidos com SQLite.
- Leitura no site validada sem regressões.
- Fila remota de trabalho e compatibilidade Chrome/extension redesenhadas antes de abrir Discovery remoto.
