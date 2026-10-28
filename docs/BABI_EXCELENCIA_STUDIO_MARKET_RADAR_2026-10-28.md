# Babi · Excelência Studio — auditoria competitiva e Sprint Market Radar 2026-10-28

## Diagnóstico honesto

**O mecanismo atual de busca ainda não supera os líderes do mercado.** Tem um embrião diferencial regional (cruzar descoberta TikTok, sinais reais de posição de bestseller no Mercado Livre e histórico no Neon), mas ainda faltam cobertura, dados comerciais verificáveis, agendamento, enriquecimento dos detalhes e identificação cross-marketplace para servir decisões de compra.

## Referências consultadas em 28/10/2026

- **FastMoss:** filtros por dia/semana/mês, product/creator/shop rankings, analytics e acesso até 180 dias dependendo do plano: https://www.fastmoss.com/pricing
- **Kalodata:** tendências de produtos TikTok Shop, criadores, livestreams, comparação de produtos e concorrentes: https://open.kaloboost.com/
- **Mercado Livre /highlights:** top 20 bestsellers por categoria **sem contagem de vendas no endpoint**: https://developers.mercadolivre.com.br/pt_br/gerenciamento-perguntas-respostas/mais-vendidos-no-mercado-livre
- **Mercado Livre /trends:** atualização **semanal** e 50 buscas, não é volume de vendas por produto: https://developers.mercadolivre.com.br/pt_br/tendencias
- **Mercado Livre /visits:** recurso oficial de visitas, disponibilidade prática depende de autorização, escopo e tipo de anúncio; registros atuais da Babi já encontraram HTTP 403: https://developers.mercadolivre.com.br/pt_br/como-comecar/recurso-visits
- **Shopee afiliados:** portal anuncia produtos mais vendidos em 7 dias, e métricas da própria performance de afiliado; não prova acesso público a vendas de todos os concorrentes: https://help.shopee.sg/portal/10/article/191692-Navigating-Shopee-Affiliate-Portal

## Alterações entregues neste sprint (branch; sem promoção manual à produção)

- `GET /api/v2/market-radar/sales-window?hours=48|168|720&sort=rising|ranking|recent|price_low|price_high&top=5|10|20`.
- Sinal novo: `rank_movement`, calculado somente se há duas ou mais observações oficiais com horários distintos do mesmo produto e categoria; `observation_count`, `first_observed_in_window`, `last_observed_in_window`.
- UI Market Radar com filtro **Subindo no ranking**, posição atual, mudança de posições e contagem de observações.
- `units_sold_in_window` e `visits_in_window` continuam `null` — **não temos fonte com acesso efetivo para vendas/visitas exatas de concorrentes**. Nenhuma venda estimada é apresentada como fato.
- Testes novos para movimento real, insuficiência de histórico e isolamento por janela/categoria.

## Para alcançar excelência comercial

1. Conector oficial autorizado (ou export com origem verificável) que forneça `units_sold`, `metric_window_start/end`, `metric_scope` (listing/seller/affiliate), `source_authority`, `observed_at` e `evidence_id`. **Nunca aceitar números sem janela, escopo ou procedência.**
2. Captura agendada e consistente de posições de ranking e preços. Comparação sem snapshots suficientes deve informar `INSUFFICIENT_HISTORY`.
3. Deduplicação cross-marketplace por evidência de identidade (EAN/GTIN/modelo), preservando anúncios distintos.
4. Índice de oportunidade **com pesos auditáveis**: posição, aceleração, frescor, diversidade de fontes e qualidade da evidência; não usar ranking como sinônimo de unidades.
5. UX final: filtro `Maior volume de vendas` habilitado somente com métricas autorizadas; filtro `Mais visualizados` apenas com contagem no período com origem clara; intervalos absolutos; confiança; links diretos; comparativo; export CSV de dados observados.
6. Revisão de segurança e testes do coletor e do dashboard antes de ligar novas fontes ou expor comercialmente.

## Estado das validações

A leitura do repositório e o desenvolvimento foram realizados por GitHub conectado. A tentativa de usar terminal local falhou por indisponibilidade do ambiente; nenhum teste Python/TS foi executado aqui. O status Vercel de um commit estava **pending** durante a avaliação. Não foi comprovada consulta ao Neon/produção nem foi feito deploy manual de produção. Validar CI, build e resposta real do endpoint antes de promover.
