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
5. Repita a captura: as mesmas URLs atualizam a linha existente, sem duplicar.

Somente cards dentro da área visível são lidos, no máximo 100 por solicitação.
Não há rolagem, descoberta automática, leitura de comentários ou IA. Campos não
visíveis são `null`; métricas abreviadas são mantidas como texto visível.
OPEN abre apenas a URL pública do vídeo em nova aba.

Testes: instale as dependências locais de teste DOM com `npm ci`, sem recriar o
ambiente Python. Execute `.\.venv\Scripts\python.exe -m pytest -q` e
`node --test tests/*.test.cjs`. Os testes HTTP usam porta e banco temporários.
