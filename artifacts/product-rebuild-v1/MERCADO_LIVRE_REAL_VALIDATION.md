# Mercado Livre — Primeira coleta real

Data: 2026-10-27 (UTC)

## Autorização

- OAuth autorizado e armazenado no Neon com criptografia autenticada.
- Probe oficial `/users/me`: `OK`.
- Site da conta: `MLB`.
- Nenhuma credencial foi incluída neste relatório.

## Coleta executada

- Categoria-folha: `MLB432600` — **Tesouras de Cozinha**.
- Fonte: API oficial Mercado Livre `/highlights`.
- Limite: 20.
- Run: `8ee20f78-72bc-4ac9-ab6f-d0fea457db72`.
- Resultado: `PARTIAL`.
- Rankings recebidos/persistidos: 20.
- Detalhes resolvidos: 14.
- Registros parciais: 6.
- Falhas isoladas de detalhe: 6.
- Tendências oficiais persistidas separadamente: 6, todas retornadas como
  `FASTEST_GROWING` para a categoria consultada.

Os snapshots, produtos, run record e tendências foram persistidos no Neon
Postgres. A API V2 confirmou 20 itens no Top 20 e histórico disponível a partir
da primeira observação. Como há apenas uma coleta, `history_complete=false`.

## Top 5 oficial

Os cinco primeiros rankings foram retornados pela fonte, mas vieram entre os
seis detalhes parciais. Portanto título, preço e link não foram inventados:

| Posição | Identidade da fonte | Nome/preço/link |
| --- | --- | --- |
| 1 | `MLB26644010` | Dados de detalhe indisponíveis nesta captura |
| 2 | `MLB60089412` | Dados de detalhe indisponíveis nesta captura |
| 3 | `MLBU4780209752` | Dados de detalhe indisponíveis nesta captura |
| 4 | `MLBU1968068328` | Dados de detalhe indisponíveis nesta captura |
| 5 | `MLB54081467` | Dados de detalhe indisponíveis nesta captura |

## Refresh token

O access token funciona, mas a resposta OAuth persistida não continha refresh
token (`refresh_available=false`). O payload integral não é retido nem logado,
logo não é possível atribuir uma causa com certeza sem reduzir a proteção de
segredos. A documentação oficial indica que `offline_access` é necessário para
refresh token e que uma troca por authorization code normalmente o devolve.

Antes da próxima autorização, verificar no Mercado Livre DevCenter se o app tem
o escopo `offline_access` habilitado, além das permissões mínimas de leitura.
Não foi feita nova autorização automática.

## Endpoints validados

- `GET /api/v2/market-radar/mercado-livre/top?category=MLB432600&period=1d`
- `GET /api/v2/market-radar/mercado-livre/trends?category=MLB432600`

Nenhum fluxo TikTok, Safety ou AliExpress foi acionado.
