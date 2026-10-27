# BABI Dashboard Redesign — Geral

## Escopo e compatibilidade

Reformulação visual local do dashboard. Não houve alteração em backend, rotas,
endpoints, comandos, Safety Contract, search-only, quarantine, security stop ou
Direct Video Enrichment (`PAUSED`). Nenhuma coleta foi iniciada.

IDs operacionais, listeners e atributos `data-*` foram preservados, incluindo
`searchForm`, `searchButton`, `captureButton`, `recentVideos`, `overviewVideos`,
`libraryVideos`, `productCandidates`, `quickStatus` e o fluxo de drawer.

## Arquivos alterados

- `app/static/index.html`
- `app/static/opportunities.js`
- `tests/dashboard-ui.test.cjs` (cobertura de formatação pt-BR adicionada no
  redesign anterior)

## Componentes visuais consolidados

- **Status chips:** TikTok, Companion, Backend, Sessão e Segurança.
- **Stat cards:** cards de KPI com valor tabular, borda de estado e grid
  responsivo.
- **Action bar:** a busca existente passou a ter composição de ação principal,
  foco visível e CTA secundário de captura.
- **OpportunityCard:** cabeçalho, lifecycle/momentum, métricas, sinais, WHY,
  riscos e limitações em blocos escaneáveis.
- **VideoCard:** thumbnail, creator, legenda, possível produto existente,
  métricas, chips de query/posição/completude e CTAs preservados.
- **CandidateItem:** cards compactos para nome, estado, vídeos, creators,
  evidências e dimensões já existentes.
- **DetailAccordion / EmptyState:** tratamento visual reutilizável para
  informações secundárias e ausência de dados.

## Decisões de UX/UI

- A home é organizada visualmente como: status global, resumo executivo, Top
  Opportunities/Early Watch, busca, vídeos recentes, candidatos e inteligência
  secundária/gaps.
- A inteligência de categoria que antes poluía o resumo executivo é movida para
  uma área secundária de Inteligência e gaps, mantendo o mesmo nó e integração.
- Sidebar, header, toolbar e botões receberam contraste, espaçamento, hover,
  foco e estados ativos mais consistentes.
- Cores são contidas: roxo/lilás para produto/ação, verde para saudável,
  amarelo para atenção e vermelho permanece reservado a erros existentes.
- Responsividade preservada para tablet e mobile, sem remover navegação móvel.

## Formatação de números

`formatNumber()` usa `Intl.NumberFormat('pt-BR')` para valores numéricos do
dashboard. Exemplos verificados: `11000 → 11.000`, `68500 → 68.500`,
`14900 → 14.900`, `31200 → 31.200`. IDs, URLs, datas e strings continuam
literais.

## Validação

Executado:

```text
node --test tests/dashboard-ui.test.cjs tests/opportunities.test.cjs tests/category-ui.test.cjs
```

Resultado: `16 passed`, `0 failed`.

Os testes cobrem IDs sem duplicidade, realocação de controles entre seções, RTL,
drawer, ações semânticas, oportunidades sem comandos de conteúdo, categorias e
formatação numérica.

## Limitação restante

Não fiz navegação de preview no Chrome porque a instância disponível está ligada
ao Companion/TikTok e não deve ser perturbada durante uma sessão autenticada.
A validação estrutural/DOM e os testes de UI passaram; a inspeção visual humana
no dashboard local continua recomendada como etapa final de aceitação.
