# Babi v1 — Baseline offline da Fase 2

Gerado antes de qualquer classificação da Fase 2, a partir do SQLite existente. Nenhuma coleta, navegação ou liberação de security latch foi executada.

| Medida | Valor |
| --- | ---: |
| Vídeos | 53 |
| Candidatos de produto | 8 |
| Search observations | 203 |
| Trend snapshots | 428 |
| Creators únicos ligados a vídeos | 31 |
| Queries únicas | 5 |
| Instantes distintos de observação | 23 |
| Janela temporal observada | 2026-10-21T16:23:12Z a 2026-10-25T18:18:48Z |

## Cobertura por candidato

As observações são associadas ao candidato por `product_candidate_evidence`; essa é uma cobertura local, sem afirmar que todos os cards representam produtos independentes.

| Faixa de observations por candidato | Candidatos |
| --- | ---: |
| 1 | 0 |
| 2 | 0 |
| 3 ou mais | 8 |

Distribuição exata: 3 (1), 4 (1), 5 (1), 8 (2), 11 (1), 16 (2).

## Séries numéricas já persistidas

Os aggregates `CANDIDATE` têm cobertura variável. Pontos de views existem para 7 dos 8 candidatos; likes, comments, shares e favorites possuem cobertura parcial e não serão preenchidos por inferência. O motor só calculará velocity para uma métrica com ao menos dois pontos numéricos e timestamps reais.

## Limitações de partida

- Sete dos oito candidatos conhecidos têm somente um creator associado; creator spread forte ainda não pode ser alegado.
- Os dados capturam resultados visíveis de busca e snapshots locais. Não representam publicação, vendas ou demanda total da plataforma.
- O latch global de challenge está ativo e a última bridge persistida está `unknown/unconfirmed`; esta fase inicia offline.
- Direct Video Enrichment permanece `PAUSED`.
