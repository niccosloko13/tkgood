# Auditoria offline — testes, candidates e evidências

22/10/2026. Somente leitura de dados persistidos. Sem navegação, refresh, abertura
de aba/janela, comando de coleta, detection run, revisão de vocabulário ou mudança
de thresholds. Script: `scripts/offline_candidate_audit.py`, SQLite `mode=ro` e
`PRAGMA query_only=ON`; não importa app/db nem executa migrações.

## Incidente do teste legado: conclusão verificável

HEAD local: `fd727e165bffde0987a617383fb4e7d107cd21d4`.

```text
git show HEAD:tests/test_enrichment.py
fatal: path 'tests/test_enrichment.py' exists on disk, but not in 'HEAD'
```

O caminho é não rastreado, não aparece no histórico de nenhuma referência local,
e não foi encontrada versão recuperável nos objetos Git. O usuário confirmou
que não conhece outro commit, branch ou backup exato e orientou preservar o estado
funcional. Portanto **não houve restauração exata do HEAD**.

`tests/test_enrichment.py` continua sendo a reconstrução já documentada: não é
o original recuperado. Não foi reconstruído novamente, alterado ou removido nesta
auditoria. Os testes novos permanecem em `tests/test_backlog.py`; ambos tiveram
hashes inalterados. Não foi apagada cobertura que estava passando.

A comparação de nomes de testes existentes no HEAD com os arquivos atuais não
encontrou nomes ausentes. Isso não comprova equivalência dos corpos modificados em
sprints anteriores, nem permite garantir equivalência byte a byte do arquivo
original não versionado. O problema de recuperação histórica permanece uma
limitação explícita, não uma recuperação concluída.

Suíte completa após a confirmação do usuário: **181 Python passed**, quatro
avisos de depreciação existentes; **86 Node/dashboard passed**. Logs/tasks:

- Python: `6b58c48d998f4840919526c2037eaa38`.
- Node/dashboard: `69841c5ea934412eb2a90b9514a8f0b3`.

## Os oito candidates

| ID | Nome | Status | Confidence | Vídeos / creators | Evidências | Repetições de caption* |
|---|---|---|---:|---:|---:|---:|
| 1 | Soap dispenser | observed | 42% | 1 / 1 | 14 | 10 |
| 2 | dish brush | observed | 42% | 1 / 1 | 14 | 10 |
| 3 | Burger Patty Maker | observed | 42% | 1 / 1 | 11 | 8 |
| 4 | fruit spinner | observed | 42% | 1 / 1 | 2 | 1 |
| 5 | long-handled floor brush | observed | 42% | 1 / 1 | 6 | 5 |
| 6 | 3 in 1 Window Cleaner | observed | 42% | 1 / 1 | 6 | 3 |
| 7 | Portable Dryer | observed | 42% | 1 / 1 | 6 | 3 |
| 8 | escova | corroborated | 64% | 2 / 2 | 6 | 4 |

*Entradas além da primeira com o mesmo vídeo/texto, dentro de cada candidate.
São capturas/leituras históricas distintas; não são novas fontes independentes.
Todos têm zero supporting comments de identidade. Alias normalizado de cada
candidate corresponde ao próprio nome; não há conjuntos de sinônimos verificados.

### Possíveis falsos positivos e ambiguidade

- Soap dispenser e dish brush vêm da mesma caption: “Soap dispenser and dish brush
  in one”. São duas hipóteses/componentes de um possível item combinado, não prova
  de dois produtos físicos distintos. Não realizar merge nesta auditoria.
- Portable Dryer tem frase comercial literal, mas falta desambiguação explícita
  do uso/modelo na frase extraída. Pode ser mais amplo do que o flag atual informa.
- Window Cleaner, floor brush, fruit spinner e Burger Patty Maker são termos
  descritivos sustentados por caption. Uma única origem não confirma modelo,
  marca, loja, SKU ou identidade física. Permanecer observed é coerente com os dados.
- `broad_concept` atual reconhece nomes compostos somente dos heads configurados.
  Por isso escova é true, mas Portable Dryer é false. **False não garante
  especificidade suficiente**. O diagnóstico é estreito e não afeta a fórmula.
- Não há fundamento para classificar algum desses vídeos como fraude, spam ou
  definitivamente incorreto apenas pelo texto persistido. São riscos de granularidade,
  ausência de independência adicional e interpretação, não falsidades comprovadas.

## Escova: risco de corroboração lexical excessiva

Estado persistido: 2 vídeos, 2 creators, 64%, zero supporting comments,
broad_concept=true, strong_explicit_phrase=false, regra satisfeita **A**.

| Grupo | Creator | Frase extraída / normalizada / alias | Caption |
|---|---|---|---|
| video:39 | @isadoravalebr | escova | Essa escova elétrica gira sozinha e ajuda a limpar rejunte, cantos e sujeira grudada sem tanto esforço. |
| video:40 | @vitrineglei | escova | escova elétrica 9 em 1, limpeza profunda, cabo extensível, banheiro, cozinha, piso, box e rejunte |

- [Vídeo 39](https://www.tiktok.com/@isadoravalebr/video/7657730138993446151)
  · [creator](https://www.tiktok.com/@isadoravalebr).
- [Vídeo 40](https://www.tiktok.com/@vitrineglei/video/7673992589036506388)
  · [creator](https://www.tiktok.com/@vitrineglei).

Seis registros textuais estão distribuídos em dois grupos independentes; o detail
adicional do vídeo 39 não criou uma terceira origem. O score é exatamente:
**0,42 base + 0,12 segundo vídeo + 0,10 segundo creator = 0,64**.
Comentários e search query acrescentam zero neste caso.

A regra A verifica apenas os mínimos de vídeos e creators. A especificidade forte
e os comentários pertencem à regra B, que é alternativa, não requisito da A.
`broad_concept` não funciona como gate nem limita o bônus. Assim, **duas captions
com um substantivo amplo bastam para mudar status e acrescentar 22 pontos**.

Diagnóstico: há risco real de supercorroboração **do conceito lexical**, quando a UI
é interpretada como identificação de um produto físico. Os textos são compatíveis
com escovas elétricas de limpeza, mas não demonstram que os itens sejam o mesmo
modelo. Dois usernames distintos também não comprovam independência econômica ou
organizacional; essa independência não foi validada nos dados disponíveis.

64% é resultado determinístico da fórmula, não probabilidade calibrada de ser o
mesmo produto físico. Nenhuma correção, downgrade, alteração da regra A, threshold,
weight, broad flag ou status foi aplicada. Uma futura revisão deve decidir a unidade
de identidade e a exigência de especificidade; não foi implementada agora.

## Qualidade das 65 evidências

- **53 captions**, **12 profile_link**. Nenhuma evidência de comentário de identidade.
- Origens: 42 search_observations, 11 video_detail_observations,
  12 creator_profile_observations.
- Zero dedup_keys duplicadas. Zero falhas nos checks de texto, URL de origem,
  timestamp, versão, existência do source row e igualdade da caption com o source.
- As 53 entradas de caption correspondem a apenas **8 pares distintos vídeo/texto**
  globais. Dentro dos candidates há 44 repetições históricas adicionais; a caption
  compartilhada por soap dispenser/dish brush participa de duas hipóteses.
- Repetições preservam histórico, mas o número bruto 65 não representa 65 fontes.
  O agrupamento atual mantém os sete candidates de uma origem em 42%.
- Os 12 links são contexto de perfil, com dois textos de destino observados:
  Bio.site/anyabumag e l.markable.ai/elnazhamai. As referências preservam URLs de
  redirecionamento TikTok. Nenhum destino foi aberto ou validado como loja/produto.
- Provenance estrutural consistente não valida a veracidade da caption, a existência
  de estoque, identidade física, causalidade ou independência comercial dos creators.

## As duas unresolved phrases

As duas pertencem ao **mesmo vídeo** de @airlandolists:
[7462746836533677358](https://www.tiktok.com/@airlandolists/video/7462746836533677358).
Caption: “Easy to remove the stains😏 #gadgets”.

- `vacuum cleaner`, pending: duas observações do mesmo texto/autor @zabeth53_4345
  em samples diferentes, mais referência ao comentário de @misss.don.
- `Mini Vacuum Cleaner`, normalized `mini vacuum cleaner`, pending: comentário
  de @misss.don, “Mini Vacuum Cleaner Price? very useful ✨”.

Há **três linhas de comentários**, mas apenas **dois pares autor/texto distintos**,
um vídeo e um creator. As duas sugestões se sobrepõem: não representam produtos
independentes nem suporte cross-video. O texto da caption não nomeia vacuum cleaner.
São termos para revisão, sem aprovação, merge ou conversão automática em candidate.

## Backlog e segurança

Library 45: 5 completos, 38 pendentes, 2 com falhas, 0 processando; 40 sem conclusão
integral. Cobertura válida: detail 10/45, comments 6/45, creator 17/45 (inclui reuso).
Product detection/corroboration estão completos para seis vídeos; isso não significa
seis candidates corroborated. Todos os 26 novos anteriores continuam sem conclusão
integral, embora um tenha recebido detail e comentários.

O HTTP 403 de 22/10/2026 às 12:25:59.604Z continua registrado para o vídeo 40.
Nenhum comando foi adicionado/alterado; nenhum lote foi iniciado/retomado. Não houve
reset do stop, refresh, retry de TikTok, conta, janela, headers, user-agent ou proxy.

## Preservação do SQLite: precisão da afirmação

Snapshots RO com hashes lógicos de todas as tabelas, comandos e arquivos de teste:
`data/offline_recovery_before.json`, `data/offline_recovery_after.json` e comparação
final em `data/offline_recovery_verification.json`.

Dados de negócio, observações, candidates, evidências, configurações, checkpoints,
comandos e o security stop ficaram inalterados. O processo já em execução continuou
atualizando **somente system_state.tiktok_bridge**, seu heartbeat automático local.
Portanto o arquivo SQLite **não ficou byte a byte idêntico**. Esta auditoria não
escreveu no banco e não deve alegar imutabilidade física total do SQLite ativo.

Artefato detalhado: `data/offline_candidate_audit.json`. Sem commit/engajamento.
