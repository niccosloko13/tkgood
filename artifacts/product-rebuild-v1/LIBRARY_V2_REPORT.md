# Biblioteca V2 — Etapa 5

## Entregue

- `GET /api/v2/library` é um read model paginado e somente leitura sobre vídeos e observações já persistidos.
- Parâmetros: `page`, `page_size` (1–50), `text`, `quality`, `identified`, `query`, `creator`, `sort` e o filtro interno confiável `candidate_id`.
- Ordenações disponíveis: mais recentes, mais antigos, mais visualizações e mais completos.
- A resposta da lista contém somente os campos de apresentação necessários; evidência bruta e análise avançada não acompanham cada linha.
- `GET /api/v2/library/{video_id}` oferece detalhe progressivo: observações da Babi e identificadores técnicos recolhidos.

## Experiência

- Desktop: tabela de evidências com Conteúdo, Produto, Métricas, Busca, Detectado e Qualidade.
- Mobile: a tabela torna-se lista de toque, filtros ficam recolhidos sob `Filtros` e o detalhe usa o drawer em formato de bottom sheet.
- Dados ausentes recebem copy contextual (`Sem métricas nesta captura`, `Ainda não identificado`) em vez de uma grade de traços.
- A Home mantém `Ver biblioteca` para a Biblioteca V2.
- O drawer de Oportunidades mostra `Ver evidências` somente quando há relação persistida entre o candidato e vídeos. Não há matching aproximado.

## Dados e segurança

- Nenhum read model grava, recalcula Trend Engine ou inicia coleta.
- O adaptador tolera bancos antigos que ainda não tenham tabelas de candidatos: produtos relacionados simplesmente ficam vazios.
- Browser Bridge, Safety, DiscoveryRunner, observações, extensão e Direct Video Enrichment não foram alterados.

## Validação

- Python: `25 passed` em `tests/test_api_v2.py` e `tests/test_trend_engine_v2.py`.
- JavaScript do projeto: `177 passed`.
- UI V2: `6 passed`; `npm run check` e `npm run build` passaram em `ui-v2`.
- Backend supervisionado respondeu a `/api/v2/library` com paginação real (`83` registros, página limitada a `3`) e o detalhe de um vídeo retornou qualidade, observações e campos técnicos.
- Estado de desenvolvimento ao final: backend saudável, extensão/bridge conectadas e aba TikTok presente. Esta etapa não emitiu comandos de conteúdo.

## Limitações conhecidas

- Não há renderizador visual independente configurado neste ambiente e a validação por Computer Use foi explicitamente removida do fluxo Babi; portanto não foram geradas screenshots nesta etapa. A validação foi feita por build, testes e respostas HTTP reais.
- A Biblioteca não infere categoria nem cria relações novas. Resultados mínimos seguem acessíveis por filtro, sem ganhar destaque.
- O filtro de candidato só aparece como navegação quando o vínculo já está persistido. A execução atual pode não ter vídeos vinculados a todas as oportunidades, o que é corretamente tratado como ausência de evidência.

## Próximo passo

Parar aqui conforme o escopo: Biblioteca V2 fecha o ciclo TikTok. Market Radar permanece fora desta etapa.
