# UI V2 — Etapa 2

## Ambiente

O problema original não era ausência de Vite ou TypeScript no projeto: a
primeira inspeção ocorreu antes de `npm install` terminar, deixando a instalação
local incompleta. Depois de concluir a instalação, `node_modules/.bin` contém
`vite(.cmd)` e `tsc(.cmd)`. A checagem seguinte revelou somente a ausência de
tipos de React, corrigida com `@types/react` e `@types/react-dom` como
`devDependencies` locais. Nenhum binário global foi usado.

`npm run check` e `npm run build` passam. `npm run dev` iniciou o Vite em
`localhost:5173`; um probe HTTP de outro processo isolado do terminal não
alcançou essa sessão, portanto essa limitação não foi tratada como falha do
Vite.

## Home V2 conectada

A Home agora consome `GET /api/v2/home`, um adaptador somente-leitura que usa
dados persistidos existentes. Ela não inicia coleta, não chama o bridge, não
recalcula inteligência nem expõe diagnósticos internos.

- KPIs: vídeos únicos, vídeos detectados pela Babi nas últimas 24h, produtos
  identificados e oportunidades do read model.
- Oportunidades: no máximo três, com lifecycle, movimento, saturação, spreads e
  explicações já produzidas pelo Trend Engine.
- Descobertas: no máximo cinco, omitindo registros sem conteúdo apresentável e
  sem fabricar métricas ausentes.
- Última missão: resumo da missão `viral-products-72h`, quando disponível.
- Estados: carregamento, erro, vazio, parcial e conteúdo normal.
- Apresentação: PT-BR, formatação centralizada de números e linguagem
  "Detectado pela Babi" para `first_seen_at`.

As páginas Descobrir, Oportunidades, Biblioteca e Sistema continuam skeletons
intencionais nesta etapa. Os botões da Home somente navegam para esses skeletons;
não duplicam nem disparam lógica do dashboard legado.

## Validação

- `npm run check`: passou.
- `npm run build`: passou.
- `npm test`: 2 testes leves de contrato/apresentação passaram.
- Testes Python focados de API, sessão e Trend Engine: 22 passaram.
- Regressão Python completa: 559 passaram (7 avisos de depreciação existentes).
- Regressão JavaScript existente: 177 passaram.
- Estado final pelo read model de sessão: `Conectado`, `SESSION=CONFIRMED`,
  `PAGE=HEALTHY`, `SECURITY=OK`, modo `SEARCH_ONLY`.

## Limitação visual

Não foram criadas screenshots nesta etapa: a política operacional anterior
proíbe usar Computer Use/inspeção externa do Chrome para validar a conexão da
Babi, e não há um renderer local independente configurado no projeto. A Home
foi validada por compilação, contrato HTTP e testes de componentes de fonte; a
captura visual deve ser feita numa etapa de QA local explicitamente autorizada.

## Refinamento visual e mobile — Home V2

O segundo passe tratou a Home como uma superfície de decisão, não como um painel
técnico.

- O cabeçalho perdeu o chip fraco de "Dados da biblioteca" e ganhou o **Pulso da
  Babi**, calculado somente da lista existente de oportunidades: total de sinais,
  quantos estão ganhando força e quantos pertencem aos estados iniciais.
- A primeira oportunidade agora é o **Principal sinal**, em card amplo com nome
  amigável quando existe mapeamento explícito seguro, nome original como contexto,
  spread de busca/creators, observações e WHY real.
- As demais oportunidades são compactas e deliberadamente secundárias.
- A missão histórica é apresentada como **Descoberta de sinais emergentes**; o
  identificador interno permanece inalterado e a interface não promete que o
  TikTok publicou algo em 72 horas.
- Descobertas recentes foram limitadas a três e agora exigem thumbnail, creator
  ou caption, e produto identificado ou métrica visível. Thumbnail isolada fica
  na Biblioteca, não ocupa a Home.
- KPIs foram reduzidos a valor e rótulo; a explicação longa não compete pelo
  espaço da decisão.
- Em telas até 768px, a sidebar é substituída por navegação inferior fixa:
  Início, Descobrir, Oportunidades, Biblioteca e Mais. Sistema permanece no menu
  secundário. Touch targets têm pelo menos 44px e a área segura é respeitada.
- Foram adicionados foco visível, `prefers-reduced-motion`, skeleton sem salto de
  layout e estados humanos para ausência/erro.

### Dados reais na validação

No momento da verificação, a API retornou 83 vídeos, 28 detectados no dia, um
produto identificado, três sinais fortes e Pulso de três sinais — dois ganhando
força. Esses valores são lidos; nenhum foi criado para apresentação.

### Verificação adicional

- `tests/test_api_v2.py`: 3 passaram.
- `ui-v2 npm test`: 3 passaram (Pulso, oportunidade principal, dados pobres,
  PT-BR, estados de ausência e navegação móvel).
- `npm run check` e `npm run build`: passaram.

Screenshots permanecem pendentes: não há renderer visual independente configurado
e esta etapa preservou a restrição de não usar Computer Use para o fluxo Babi.

## Discovery V2

Descobrir passou a consumir seu próprio read model e ações V2. A tela oferece
busca manual, objetivos derivados de query packs existentes, progresso humano,
resumo de execução e desempenho real por query. Consulte
`DISCOVERY_V2_REPORT.md` para o contrato, as restrições de autorização e os
resultados de teste.

## Oportunidades V2

Oportunidades agora é uma tela de priorização sobre o read model persistido do
Trend Engine, com destaque, observação, saturação e drawer de análise. Consulte
`OPPORTUNITIES_V2_REPORT.md` para o contrato, os dados reais e testes.
# Atualização — Biblioteca V2 (Etapa 5)

A Biblioteca V2 foi conectada a um read model paginado, com tabela desktop, lista mobile, filtros de dados persistidos e drawer de evidência. O detalhe de implementação, validação e limitações está em `LIBRARY_V2_REPORT.md`.
