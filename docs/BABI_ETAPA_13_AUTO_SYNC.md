# BABI — ETAPA 13.1 — Sincronização automática TikTok PC → Neon → Vercel

**Branch:** `feat/babi-product-rebuild-v1`  
**Status:** código implementado, **não ativado em produção** e **sem teste de envio real nesta execução**.

## O que está pronto no código

- `scripts/auto_sync_tiktok_neon.py`: worker local, sem navegador, que lê a Biblioteca V2 do SQLite em modo somente leitura e cria uma fila SQLite própria em `data/tiktok_neon_outbox.db`.
- Verifica alterações por checksum SHA-256; não reenvia vídeos idênticos já confirmados e deduplica cada `video_id`.
- Envia até 50 vídeos por lote ao endpoint `POST /api/v2/tiktok-sync/videos`, exige resposta com `accepted` equivalente ao lote e então confirma a entrega localmente.
- Em falhas ou interrupção a fila permanece em disco e tenta novamente em ciclos posteriores. Sem alterar comandos da extensão, controle do Chrome ou missões.
- `tests/test_tiktok_auto_sync.py`: testes criados para projeção segura, deduplicação, reenvio de atualização e confirmação.
- `GET /api/v2/tiktok-sync/status`: leitor do servidor informa total sincronizado e última sincronização, depois da implantação do backend.
- `BABI_TIKTOK_NEON_READS=1`: chave de ativação separada para trocar apenas a **Biblioteca** ao espelho do Neon. Deve ficar desativada até comparar dados.

## Configuração obrigatória

**No Vercel**, configurar `BABI_TIKTOK_SYNC_TOKEN` com segredo aleatório de pelo menos 32 caracteres, somente como variável protegida de backend. Não publicar no frontend nem enviar a ninguém. `OAUTH_DATABASE_URL` já existe no ambiente hospedado e é usada pelo espelho no Neon.

**No PC coletor**, configurar:
- `BABI_TIKTOK_SYNC_URL=https://babi-product-hunter.vercel.app`
- `BABI_TIKTOK_SYNC_TOKEN` com o mesmo valor protegido do servidor.

O segredo nunca deve ir ao repositório nem aos logs. **Não usar a variável `BABI_TIKTOK_NEON_READS` antes da primeira validação.**

## Operação local (Windows PowerShell)

Na pasta do projeto atualizado:

```powershell
git fetch origin
git switch feat/babi-product-rebuild-v1
git pull --ff-only origin feat/babi-product-rebuild-v1
python -m pytest tests/test_tiktok_neon_mirror.py tests/test_tiktok_auto_sync.py -q
python -m scripts.auto_sync_tiktok_neon --dry-run --once
```

O dry run não envia dados à rede, embora possa criar/atualizar a fila local.

Após revisão do Preview, deployment controlado, variáveis de ambiente protegidas e testes positivos:

```powershell
python -m scripts.auto_sync_tiktok_neon --once
```

Conferir `GET /api/v2/tiktok-sync/status` no deployment de destino e comparar a contagem com o SQLite local. Em seguida, usar modo contínuo **no PC**:

```powershell
python -m scripts.auto_sync_tiktok_neon --interval 90
```

O loop depende do PC ligado e do terminal/processo ativo. Para iniciar com Windows Task Scheduler, cadastrar um processo controlado que execute o worker; **nenhum agendamento foi criado automaticamente**.

## Validação exigida antes de publicar a troca de leitura

1. Executar teste específico e suite geral Python, TypeScript, UI e build.
2. Conferir Preview, token do backend e resultado do primeiro lote pequeno.
3. Validar que `GET /api/v2/tiktok-sync/status` aumenta a contagem e atualiza o timestamp.
4. Confirmar que os vídeos foram apresentados com títulos, métricas e evidências corretamente, sem vazamento de sessão.
5. Somente então ativar `BABI_TIKTOK_NEON_READS=1` e validar a Biblioteca completa na Vercel.

## Limitações reais

- **Ainda não sincroniza Home, Discovery, Oportunidades, comentários detalhados ou o estado do worker;** apenas os campos da biblioteca. Não existe fila remota para comandar o navegador do PC.
- Vídeos podem ser visíveis no site somente depois de cada ciclo, não em tempo real.
- Não representa coleta do TikTok executada na Vercel.
- O espelho Neon é uma coleção separada. Não substituir nem apagar o SQLite, nem alterar o Mercado Livre.
- Proteger o painel que expõe dados internos antes de torná-los publicamente disponíveis.
- A própria primeira implantação e sincronização exigem testes no ambiente autorizado; não afirmar que já estão operacionais.

**Preservar TikTok Safety, DiscoveryRunner, OAuth, Neon Market Radar, 93 posições oficiais, Shopee/AliExpress e credenciais.**
