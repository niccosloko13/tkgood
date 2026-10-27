# API V2 — Etapa 2

## Endpoint criado

`GET /api/v2/home`

É um read model de Home. Ele somente lê SQLite e adapta dados existentes para a
UI V2; não agenda comandos, não invoca extensão/bridge, não altera Safety,
DiscoveryRunner, observações, candidatos ou Trend Engine.

## Contrato

```json
{
  "generated_at": "ISO-8601",
  "summary": {
    "library_videos": 0,
    "recently_detected": 0,
    "identified_products": 0,
    "strong_signals": 0
  },
  "top_opportunities": [],
  "recent_discoveries": [],
  "last_mission": null,
  "data_freshness": { "last_observation_at": null }
}
```

`recently_detected` significa vídeos cuja primeira detecção pela Babi ocorreu
nas últimas 24 horas; não representa a data de publicação no TikTok.

`identified_products` conta candidatos com nome canônico e estado
`corroborated`, `promoted` ou confirmação manual. `strong_signals` é a
quantidade (limitada a três para a Home) de oportunidades já persistidas no read
model do Trend Engine; não introduz score novo.

## Dados parciais

A qualidade de apresentação (`COMPLETE`, `PARTIAL`, `MINIMAL`) é exclusivamente
uma dica de renderização. Ela não altera evidência científica, lifecycle ou
ranking. Métricas ausentes são omitidas do contrato de descoberta.

## Testes

`tests/test_api_v2.py` cobre banco vazio, dados persistidos, campos parciais,
missão ausente/presente, limite de três oportunidades e ausência de escrita do
adaptador.
