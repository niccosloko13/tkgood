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

## Correção de detalhes (Etapa 8.2)

O resolver de `PRODUCT` tratava o retorno oficial como resolvido, mas procurava
somente `title`. Produtos de catálogo usam `name`, e não representam uma oferta
individual: preço e permalink podem não existir. A normalização foi corrigida e
os 20 registros persistidos foram reconsultados por endpoints oficiais, sem
nova coleta de ranking.

- Recuperados: 14 de 20 (70%).
- Permanecem parciais: 6 de 20 (30%).
- Os seis são `USER_PRODUCT` e todos retornaram `HTTP 403` no endpoint oficial
  `/user-products/{id}` para esta credencial.
- Não houve 404, ID reinterpretado, preço ou URL inventados.

### Cinco produtos com dados oficiais disponíveis

| Posição | Produto | Preço/link |
| --- | --- | --- |
| 1 | Tesoura Supercort 8 Polegadas Tramontina | Não disponível no catálogo |
| 2 | Kit 3 Tesouras de Aço Inox Multiuso | Não disponível no catálogo |
| 5 | Tesoura de Cozinha Preta We Varejo | Não disponível no catálogo |
| 6 | Tesoura Tramontina de Aço Inox 8 | Não disponível no catálogo |
| 7 | Tesoura Profissional de Cozinha para Frango/Peixe | Não disponível no catálogo |

### Falhas remanescentes

`MLBU4780209752`, `MLBU1968068328`, `MLBU5065646851`, `MLBU4396956254`,
`MLBU1446588474` e `MLBU4325935739`: `USER_PRODUCT_HTTP_403`.

Esses IDs permanecem como User Products; não foram convertidos para ITEM e não
foram usados endpoints de scraping ou caminhos não suportados.

## Refresh token

O access token funciona, mas a resposta OAuth persistida não continha refresh
token (`refresh_available=false`). A URL OAuth atual não solicita `scope`
explicitamente; a concessão depende das permissões configuradas no DevCenter.
Como o payload original não é retido nem logado, não é possível provar
retroativamente se `offline_access` foi concedido nesta autorização.

A documentação oficial indica que o fluxo Authorization Code com
`offline_access` retorna `refresh_token`. Assim, a hipótese operacional é
escopo offline não habilitado/concedido, mas isso ainda não é uma certeza.

Antes de uma próxima autorização, verificar no Mercado Livre DevCenter se o app
tem o escopo `offline_access` habilitado junto de `read`, sem adicionar `write`.
Se estiver ausente, salvar e solicitar uma nova autorização humana; não houve
nova autorização automática nesta etapa.

## Endpoints validados

- `GET /api/v2/market-radar/mercado-livre/top?category=MLB432600&period=1d`
- `GET /api/v2/market-radar/mercado-livre/trends?category=MLB432600`

Nenhum fluxo TikTok, Safety ou AliExpress foi acionado.

## Fechamento de integraÃ§Ã£o (Etapa 8.3)

### Grant e renovaÃ§Ã£o OAuth

Em 27/10/2026, o runtime hospedado consultou o recurso oficial
`GET /applications/{APP_ID}/grants` usando o bearer armazenado somente no
servidor. A resposta foi reduzida antes de sair do servidor: nenhum token e
nenhum identificador de usuÃ¡rio foram retornados ou registrados.

- Grants encontrados: 1.
- `read`: concedido.
- `offline_access`: **nÃ£o concedido**.
- `write`: consta no grant existente, embora a Babi nÃ£o o use nem o solicite.

Isso fornece a causa operacional para `refresh_available=false`: sem
`offline_access`, a API nÃ£o tem obrigaÃ§Ã£o de retornar `refresh_token`. O parser
jÃ¡ aceita e persiste o campo quando ele existe, mas o payload histÃ³rico bruto
nÃ£o Ã© retido por design; portanto nÃ£o Ã© possÃ­vel reproduzir sua ausÃªncia
retroativamente. A persistÃªncia agora registra, sem guardar o token, se uma
prÃ³xima resposta trouxe `refresh_token`.

**AÃ§Ã£o manual necessÃ¡ria no DevCenter antes de uma nova autorizaÃ§Ã£o:** deixar o
app no modo de somente leitura, habilitar/conceder `offline_access` junto de
`read` e revisar/remover permissÃµes de escrita que nÃ£o sejam necessÃ¡rias. Depois
disso, uma nova autorizaÃ§Ã£o humana deve ser iniciada manualmente. A URL OAuth
agora solicita explicitamente `scope=read offline_access` e nunca solicita
`write`; esta etapa nÃ£o iniciou uma nova autorizaÃ§Ã£o.

### Estados de detalhe comercial

Os 20 rankings oficiais permanecem preservados na ordem da fonte. A API de Top
20 agora expÃµe, separadamente da posiÃ§Ã£o oficial, os campos
`detail_status`, campos disponÃ­veis/ausentes e `exploration_priority`, para que
uma UI futura possa priorizar conteÃºdo rico sem reordenar o ranking Mercado
Livre.

| Estado | Quantidade | EvidÃªncia real |
| --- | ---: | --- |
| `DETAILS_AVAILABLE` | 0 | exigiria nome, imagem, preÃ§o e URL oficiais |
| `DETAILS_PARTIAL` | 14 | nome e imagem de catÃ¡logo; preÃ§o e URL indisponÃ­veis |
| `DETAILS_RESTRICTED` | 6 | `USER_PRODUCT_HTTP_403` no endpoint oficial |

O `HTTP 403` dos seis User Products Ã© classificado como detalhe restrito; a
causa precisa (escopo, titularidade, polÃ­tica do recurso ou outra restriÃ§Ã£o da
API) continua nÃ£o confirmada. NÃ£o houve tentativa de contorno, scraping ou
reinterpretaÃ§Ã£o desses IDs como ITEM.

O Top 20 hospedado foi validado depois da alteraÃ§Ã£o: as primeiras entradas
recuperadas tÃªm nome e imagem, mas continuam sem preÃ§o/permalink. Portanto
"nome recuperado" nÃ£o Ã© tratado como "produto comercial completo".
