# Oportunidades V2 — Etapa 4

## Endpoint

`GET /api/v2/opportunities` é um adaptador somente-leitura da tabela persistida
do Trend Engine. Ele não chama recompute, não escreve em SQLite e não altera
lifecycle, momentum, saturation, prediction checkpoints ou observações.

O retorno reúne total analisado, prioridades, sinais em observação e sinais
saturados. Cada item contém apresentação humana de estado, métricas observáveis,
WHY, limitações, histórico persistido e uma seção avançada recolhível.

## Apresentação

- Um principal sinal, seguido por oportunidades compactas.
- Seções separadas para **Em observação** e **Sinais saturados**.
- Traduções humanas para lifecycle, movimento e saturação; enums internos não
  aparecem na experiência normal.
- Drawer lateral no desktop e bottom sheet no mobile.
- Análise avançada fica recolhida e mostra somente campos já existentes.
- Datas de histórico são tratadas como detecção/observação da Babi, nunca como
  publicação no TikTok.

## Dados reais verificados

No estado validado, o read model retornou 8 oportunidades persistidas: 5
prioritárias, 2 em observação e 1 saturada.

## Testes

- `tests/test_api_v2.py` + `tests/test_trend_engine_v2.py`: 23 passaram.
- `ui-v2 npm test`: 5 passaram.
- `npm run check` e `npm run build`: passaram.

## Limitações

Não há novo score, inferência de publicação ou gráfico inventado. Screenshots
continuam pendentes porque não há renderer visual local independente configurado
e esta etapa preserva a restrição operacional de não usar Computer Use no fluxo
Babi.

## Próximo passo

Biblioteca V2, mantendo o mesmo padrão de read models e apresentação.
