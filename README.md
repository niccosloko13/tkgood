# Product Hunter — TikTok v0.1.4

## Arquitetura atual: Normal Chrome Bridge

A partir da v0.1.4 o TikTok NÃO é aberto pelo Playwright.

O painel abre um perfil separado do Google Chrome normal:

`browser-profiles/chrome-tiktok-main`

Uma extensão local, `Product Hunter Companion`, observa somente sinais visíveis da página
e envia heartbeat para o painel local. O botão CAPTURE RESULTS solicita uma leitura
dos cards visíveis da busca atual e armazena vídeos únicos no SQLite.

Isso evita depender do Chromium automatizado que apresentou erro de reprodução no TikTok.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Abra:

`http://127.0.0.1:8000`

## Instalar a extensão

1. No Chrome aberto pelo Product Hunter, acesse `chrome://extensions`
2. Ative **Modo do desenvolvedor**
3. Clique em **Carregar sem compactação**
4. Selecione `C:\product-hunter-tiktok-v0.1.4\extension`
5. Volte para TikTok
6. O painel deve mostrar `Chrome connected`

## Princípios

Consulte [o guia do command bridge](docs/BRIDGE.md) para ativar e testar o popup,
heartbeat e o comando SEARCH desta etapa. O backend já iniciado precisa de reinício
manual para carregar as novas rotas; a extensão também precisa ser recarregada.

- Sem Playwright controlando TikTok
- Sem stealth
- Sem alteração de `navigator.webdriver`
- Sem ocultação de automação
- Sem CAPTCHA bypass
- Sem interação social
- Extensão somente leitura
- Login permanece manual

## Read-only Search Capture

1. Após atualizar o backend, reinicie manualmente o processo existente com `python run.py`.
2. Recarregue a extensão descompactada da pasta `extension` e a aba TikTok.
3. No painel, execute TEST SEARCH `home gadgets` e aguarde os resultados no Chrome.
4. Clique CAPTURE RESULTS. VIDEOS mostra o total único; RECENT VIDEOS exibe os últimos 20.
5. Repita a captura: o mesmo video_id mantém a identidade e adiciona uma observação histórica.

Somente cards dentro da área visível são lidos, no máximo 100 por solicitação.
Na captura de busca não há rolagem, descoberta automática ou IA. Campos não
visíveis são `null`; views preserva o texto original e o valor inteiro normalizado.
OPEN abre apenas a URL pública do vídeo em nova aba.

Testes: instale as dependências locais de teste DOM com `npm ci`, sem recriar o
ambiente Python. Execute `.\.venv\Scripts\python.exe -m pytest -q` e
`node --test tests/*.test.cjs`. Os testes HTTP usam porta e banco temporários.

## Search Result Enrichment

RECENT VIDEOS mostra thumbnail quando disponível, creator, caption, views,
posição na captura visível, busca, completude e OPEN. EXTRACTION QUALITY mostra
coverage da última captura e quantidades Complete/Partial/Minimal.

Os contadores são separados: Library videos (todos os únicos do histórico),
Current capture (última captura concluída), New this capture (novos inseridos)
e Updated / duplicates (vídeos conhecidos observados novamente). O extrator
atual é `tiktok-search-card-v2`; recarregue a extensão **e a aba TikTok** ao atualizar.

A identidade está em `videos`; o histórico por captura está em
`search_observations`. A migração importa os dados antigos uma única vez e mantém
a tabela antiga intacta. Não resete o banco. Veja [EXTRACTION.md](docs/EXTRACTION.md)
para provenance, confidence, precedence, versionamento e critérios de cobertura.
# Authorized read-only detail validation

Development reloads now use `python scripts/devctl.py reload-all`; individual
commands are `status`, `restart-backend`, `reload-extension`, and `refresh-tiktok`.
Use the existing `.venv`. No Computer Use or chrome://extensions is needed.
See [DEV_CONTROL.md](docs/DEV_CONTROL.md) for ownership, local security and recovery.

The user authorized opening the eight captured videos sequentially to read visible
metadata and counts. `READ_VIDEO_DETAIL` accepts only an existing library video,
waits for rendered metadata, and stores separate `video_detail` evidence. It never
activates engagement controls. Search-card coverage remains independent; detail
enrichment cannot turn a failed search capture into a passing capture.

Run the bounded helper with the intended capture ID:
`python scripts/read_video_details.py --capture-id command:9 --limit 8`.
It stops on the first failed read. Real commands #13–#20 read all eight videos:
creator and caption 8/8. The subsequent `tiktok-video-detail-v2` numeric validation
collected likes/comments in 7/8 videos, shares in 8/8 and favorites in 7/8. Views
stayed null in detail. See [VIDEO_DETAIL_METRICS.md](docs/VIDEO_DETAIL_METRICS.md)
for raw/normalized examples, loading-placeholder evidence and limitations.
This does not change search-card coverage or close its outstanding acceptance gate.

## Comments sampling read-only

VIDEO DETAIL agora oferece SAMPLE COMMENTS (30), com sinais objetivos da última
amostra. `python scripts/sample_comments.py VIDEO_URL --target 30` faz a mesma
leitura pela ponte; o limite absoluto é 100. Somente vídeos já capturados e
enriquecidos são aceitos. A extensão pode abrir a seção de comentários e rolar
apenas sua região, sem responder, expandir respostas ou ativar engajamento.
Campos ausentes continuam null; timestamps preservam o texto visível.
Veja [COMMENTS.md](docs/COMMENTS.md) para evidência, deduplicação e validação real.
Atualizações usam `python scripts/devctl.py reload-all` automaticamente.

## Creator / profile enrichment

Na biblioteca, clique no creator para abrir seu drawer; o drawer de vídeo também
inclui uma seção recolhível de perfil e performance. **Ler perfil no Chrome**
executa `READ_CREATOR_PROFILE` apenas para um creator observado de vídeo da Library,
lê metadados públicos e retorna ao vídeo, sem engajamento nem seguir links externos.
Creators e observações históricas ficam separados dos vídeos. Ratios, buckets e
Creator Independence são determinísticos e explicáveis, sem IA ou produto.
Veja [CREATORS.md](docs/CREATORS.md) para fórmula, provenance, limites e APIs.



## Persistent Chrome and silent local execution

Enrichment em lotes de cinco na área Coleta: estados por etapa, reutilização de
observações, parada após o vídeo atual e checkpoints. Veja
[ENRICHMENT_BACKLOG.md](docs/ENRICHMENT_BACKLOG.md) e
[revisão de escova](docs/ESCOVA_REVIEW.md). Um bloqueio de segurança persistente
impede novas navegações; não limpe o bloqueio para completar o backlog.

Use `scripts/background_runner.py` for fixed background tasks and
`scripts/devctl.pyw` with the existing pythonw launcher. Logs remain in
`.runtime/logs`. See [Persistent runtime](docs/PERSISTENT_RUNTIME.md).
