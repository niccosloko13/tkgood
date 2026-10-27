# Discovery V2 — Etapa 3

## Endpoints

- `GET /api/v2/discovery` fornece um read model de conexão simples, execução
  ativa, última execução, presets e desempenho de buscas.
- `POST /api/v2/discovery/search` adapta a busca manual para o
  `DiscoveryRunner` Stage 1 já existente, search-only e limitado.
- `POST /api/v2/discovery/mission` usa somente uma autorização Stage 2 já
  persistida e exatamente compatível com o preset. Não cria autorização,
  recovery, desbloqueio ou retry.

## Experiência

- Busca manual com campo único e CTA claro.
- Cinco objetivos derivados do query pack existente: Produtos ganhando força,
  Casa, Cozinha, Limpeza e Gadgets.
- Card de andamento mostra apenas progresso humano: busca atual, total, novos,
  conhecidos, resultados e produtos identificados quando a relação persistida
  existe.
- Resumo final reutiliza números persistidos de uma execução concluída.
- Desempenho mostra `novos / total` como percentual observável, sem score.
- Quando a conexão não está pronta, a tela não tenta iniciar nada e orienta a
  abrir Sistema.

## Segurança e limites

Nenhuma regra de Safety, Browser Bridge, Target Safety, DiscoveryRunner,
search-only, Trend Engine, SQLite ou extensão foi alterada. A ação de missão
fica indisponível na prática quando não existe autorização explícita prévia;
isso é uma limitação deliberada do contrato, não um bypass da UI.

## Mobile

Descobrir segue o design system da Home. Em telas pequenas: busca em largura
total, CTA de 48px, presets verticais, progresso full-width e a navegação
inferior existente.

## Verificação

- `tests/test_api_v2.py`, `tests/test_discovery.py` e
  `tests/test_discovery_runner.py`: 20 passaram.
- `tests/test_safe_collection.py`: 20 passaram.
- `ui-v2 npm test`: 4 passaram.
- `npm run check` e `npm run build`: passaram.

## Limitações

Não foram geradas screenshots: não há renderer visual local independente
configurado e esta etapa preserva a restrição operacional de não usar Computer
Use no fluxo Babi. A UI foi validada por build, contrato HTTP e testes.

## Próximo passo

Reconstruir Oportunidades V2 como próxima tela, usando apenas read models do
Trend Engine já existente.
