# Sistema V2 — Etapa 6

## Endpoint e modelo

- Criado `GET /api/v2/system`, estritamente de leitura.
- O modelo adapta o estado canônico da conexão, sessão e segurança para labels humanos. Ele não libera latch, solicita recovery, abre navegador, inicia descoberta ou modifica o banco.
- Diagnósticos técnicos (bridge, heartbeat, URL atual, estados de página/sessão, latch e build) permanecem apenas no campo `diagnostics`, mostrado recolhido na UI.

## Tela

- Cabeçalho com estado geral: `Tudo funcionando normalmente` ou `Ação necessária`.
- Cartões de Babi, Navegador, TikTok, Sessão e Segurança usam apenas estados humanos.
- `Leitura direta de vídeos` fica em Sistema: quando pausada, esclarece que a pesquisa continua disponível normalmente.
- Qualidade da biblioteca mostra totais de vídeos completos, parciais e mínimos como classificação de apresentação.
- Eventos recentes são traduzidos para mensagens legíveis; mensagens e stack traces brutos não aparecem na camada principal.
- `Diagnóstico avançado` e `Laboratório` são accordions. Fontes externas são estrutura visual futura, sem integrações de marketplace.
- Em mobile, cartões ficam em grade/coluna, eventos e accordions não usam tabelas largas.

## Validação

- Python: `27 passed` em `tests/test_api_v2.py` e `tests/test_trend_engine_v2.py`.
- UI V2: `7 passed`.
- `npm run check` e `npm run build` passaram em `ui-v2`.
- Backend reiniciado pelo supervisor e saudável.
- Consulta real a `/api/v2/system`: navegador conectado, TikTok pronto, sessão confirmada, nenhum bloqueio ativo, Direct Video Enrichment pausado, 83 vídeos na biblioteca e 5 eventos recentes.

## Limitações

- O backend é reportado como disponível pelo read model que está servindo a resposta; não há novo monitor externo nem fluxo de recovery nesta etapa.
- Não existe renderizador visual independente configurado e a validação via Computer Use não faz parte do fluxo Babi. Por isso não foram produzidos screenshots; validação foi feita por build, testes e HTTP real.
- Gold Set, identificação visual, OpenCLIP, FAISS e inteligência experimental são apenas referências de laboratório, sem nova integração.

## Próximo passo

Parar aqui conforme o escopo. Market Radar não foi iniciado.
