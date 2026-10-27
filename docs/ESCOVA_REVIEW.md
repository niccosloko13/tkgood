# Revisão diagnóstica: escova

Retrato anterior ao enrichment do backlog: `data/escova_before_backlog.json`.
Somente dados persistidos; nenhuma navegação foi usada para produzir esta revisão.

## O que causou a corroboração

Candidate #8, canonical/normalized/signature `escova`, status corroborated,
confidence 0,64. Alias observado: `escova`; nenhum alias novo foi inventado.

A regra A existente exige dois vídeos independentes e dois creators independentes.
Foi satisfeita com os grupos `video:39` e `video:40`. As cinco evidências brutas
de caption representam apenas **dois** grupos independentes, não cinco origens.
Não há supporting comments na evidência que originou esta corroboração.

Fórmula inalterada: base identity 0,42 + segundo vídeo 0,12 + segundo creator 0,10
= **0,64**. Sem bônus de comentários ou query. Source diversity score: 50.

## Vídeos e textos originais

| Vídeo Library | Creator | Raw phrase extraída | Normalized phrase |
|---|---|---|---|
| 39 / 7657730138993446151 | @isadoravalebr | escova | escova |
| 40 / 7673992589036506388 | @vitrineglei | escova | escova |

[Vídeo de @isadoravalebr](https://www.tiktok.com/@isadoravalebr/video/7657730138993446151)
— [perfil](https://www.tiktok.com/@isadoravalebr).

Caption persistida: “Essa escova elétrica gira sozinha e ajuda a limpar rejunte,
cantos e sujeira grudada sem tanto esforço.”

[Vídeo de @vitrineglei](https://www.tiktok.com/@vitrineglei/video/7673992589036506388)
— [perfil](https://www.tiktok.com/@vitrineglei).

Caption persistida: “escova elétrica 9 em 1, limpeza profunda, cabo extensível,
banheiro, cozinha, piso, box e rejunte”.

O primeiro vídeo tinha três evidências de caption; o segundo, duas. São aparições
persistidas em capturas distintas/repetidas. O grafo conserva cada provenance;
o agrupamento de diversidade impede que isso conte como cinco vídeos.
URLs e textos completos permanecem no snapshot, junto aos source entity IDs,
timestamps, confidences e extractor version de cada evidência.

## Conclusão e limite

Os dois textos descrevem escovas elétricas para limpeza e sustentam uma hipótese
de conceito comercial comum. A extração conservou somente o substantivo `escova`,
perdendo modificadores úteis como elétrica/giratória/9 em 1. Portanto, a regra
lexical pode reunir conceitos mais amplos do que um produto físico identificável.
Não há prova de mesmo modelo, SKU, marca, loja ou produto físico.

Foi acrescentado `broad_concept=true`, apenas diagnóstico. Não houve merge,
alteração de confidence, pesos, thresholds, regras de corroboração ou vocabulário.
O diagnóstico centralizado também verifica heads genéricos como brush, cleaner,
maker, dispenser, dryer e tool. Frases específicas que contêm esses substantivos
não são automaticamente consideradas equivalentes.

Evidência acrescentada durante o backlog deve ser consultada no relatório final;
ela não deve ser apresentada retroativamente como causa do status inicial.

## Após a tentativa de enrichment

O vídeo 39 recebeu detail e uma amostra de 30 comentários. Uma evidência textual
adicional de detail foi incorporada ao candidate; nenhum desses comentários entrou
como suporte explícito de identidade. O perfil falhou por readiness. Ao abrir o
vídeo 40, houve HTTP 403 e a coleta parou. O candidate continua com dois vídeos,
dois creators, zero supporting comments e confidence 0,64; broad_concept=true.
