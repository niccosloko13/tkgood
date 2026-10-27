# Babi UI Redesign

## Escopo

Redesenho local do dashboard sem alterações em endpoints, comandos, coleta,
Safety Contract, regras search-only ou estado de Direct Video Enrichment.

## Alterações

- Criado um pequeno sistema visual reutilizável via tokens CSS para superfícies,
  tipografia, cores de status, bordas, sombras, raios e estados de interação.
- Melhorada a hierarquia de navegação, cabeçalho, cards de métricas, seção de
  oportunidades e caixa de busca.
- Cards de métricas agora têm ênfase visual, alinhamento consistente e números
  tabulares para leitura rápida.
- Busca recebeu superfície destacada, campo com foco visível e CTAs mais claros,
  preservando os IDs `searchForm`, `searchButton` e `captureButton`.
- Vídeos recentes e biblioteca agora usam cards escaneáveis com área de thumbnail,
  creator, legenda, produto/categoria já existentes, métricas destacadas, chips
  de query/posição/completude e CTAs originais para detalhes e abertura.
- O layout continua responsivo: cards reduzem para duas colunas e uma coluna em
  telas menores; a navegação móvel existente foi preservada.

## Formatação numérica pt-BR

Foi adicionado `formatNumber()` no renderer do dashboard. Valores numéricos
visíveis agora usam `Intl.NumberFormat('pt-BR')`, incluindo métricas de vídeo,
biblioteca, capturas, perfis e oportunidades. Exemplos:

- `11000` → `11.000`
- `68500` → `68.500`
- `14900` → `14.900`

Valores textuais, URLs, datas e IDs de vídeo permanecem literais; portanto um
ID como `7673992589036506388` não é alterado.

## Arquivos modificados

- `app/static/index.html`
- `app/static/opportunities.js`
- `tests/dashboard-ui.test.cjs`

## Verificação

Executado:

```text
node --test tests/dashboard-ui.test.cjs tests/opportunities.test.cjs tests/category-ui.test.cjs
```

Resultado: `16 passed`, `0 failed`.

Os testes cobrem a ausência de IDs duplicados, a movimentação dos controles
existentes entre seções, RTL, drawer, ações semânticas e a nova formatação
numérica pt-BR.
