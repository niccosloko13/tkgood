# Atualizacao da retomada: novo HTTP 403 na home

A Companion voltou a emitir heartbeat recente, build 1db642b5c5e17f10, mesma aba 618200292/janela 618199843 e URL https://www.tiktok.com/. O transporte do worker estava conectado, mas os sinais de pagina inicialmente ausentes: content_script_connected=false, ready_state=null, sessao unconfirmed. Nao havia DOM real suficiente para alterar os seletores com fundamento.

Foi executado somente o comando existente DEV_VALIDATE_TIKTOK_HOME #47b21c4a2da115ea3bebf74487c8140a: uma recarga da home na mesma aba, sem reload de extensao, reinicio do Chrome, novo perfil ou Computer Use. O leitor respondeu transitoriamente com documento complete, porem sem pagina healthy/evidencia de conta. A tentativa terminou FAILED: Timed out waiting for refreshed TikTok content scripts.

**STOP REASON: novo HTTP 403 em https://www.tiktok.com/, observado em 2026-10-23T16:23:11.456Z.** O registro chegou ao backend antes da conclusao do comando. Nenhum novo comando de navegador foi emitido apos essa observacao.

- ROOT CAUSE atual: HTTP 403 real da home; nao e possivel tratar o incidente como apenas page-specific.
- COMPANION: worker conectado com heartbeat recente durante a tentativa; leitor DOM sem prontidao confirmada.
- HEARTBEAT: recente durante a tentativa; ver timestamps em home-validation-result.json.
- CURRENT URL: https://www.tiktok.com/.
- CURRENT PAGE: HTTP 403, evidenciado pelo novo evento de rede; sinais de pagina nao confirmaram healthy.
- SESSION STATUS: unconfirmed; nenhum estado confirmado foi fabricado nem seletor alterado sem DOM.
- SECURITY STOP: ativo para o novo 403 da home. O incidente antigo do video foi preservado em browser_security_history; nenhum clearance foi executado.
- SMOKE TEST: SEARCH/detail/comments/creator nao executados.
- DISCOVERY STATUS: zero novas sessoes/videos nesta retomada; nenhuma coleta ou enrichment.

Evidencias: home-session-diagnostics.json (antes), home-validation-result.json e security-after-home-403.json. A verificacao final foi somente leitura do banco; confirmou novo stop e incidente anterior no historico. Nenhuma mudanca de codigo nesta retomada; suites 252 Python/113 Node abaixo pertencem a implementacao anterior e nao validam a sessao real. Sem commit. Aguardar resolucao legitima do bloqueio; nao tentar novamente automaticamente.

O relatorio anterior abaixo e historico e nao descreve mais o bloqueio atual de perfil ausente.

---

# BABI — Discovery recovery

Status: correções locais concluídas e testadas; recuperação real **bloqueada pela ausência do perfil Chrome que contém a Companion**. Home, sessão, smoke e discovery não validados em produção. Sem commit.

## CONNECTION / ROOT CAUSE

- Backend saudável, gerenciado pelo supervisor; reinícios exclusivamente por `scripts/devctl.py restart-backend`, com resultado `READY`.
- A Companion `kaohbkldpeejomnmbeedchokglokbbgk` está registrada em `browser-profiles/chrome-tiktok-main/Default/Secure Preferences`, apontando para a extensão deste workspace. Esse perfil não tem processo Chrome ativo. A Companion não consta nas Preferences/Secure Preferences do perfil Default do Chrome aberto. Nenhuma configuração desses perfis foi modificada.
- As permissões registradas incluem storage, tabs, alarms, webRequest, TikTok e loopback 127.0.0.1:8000; correspondem ao manifesto. Não foi encontrada falta dessas permissões na configuração persistida.
- Último heartbeat: **2026-10-22T14:38:35.944786+00:00**. Companion **disconnected**; heartbeat **stale**. Versão histórica **0.1.5**, build histórico **d0d95f70d86508ef**. O novo build foi gerado, mas não foi confirmado carregado no Chrome.
- Service worker/content scripts/runtime messaging: sem evidência de execução atual, pois o perfil da extensão não está ativo. Mensageria, coleta dos sinais e payload real foram exercitados em testes locais; isso não substitui confirmação no navegador real.
- Loopback do backend responde normalmente. Não há heartbeat atual que permita diagnosticar erro de fetch do worker; console/erros atuais da extensão permanecem **indisponíveis**, não presumidos ausentes. Não há evidência de que CORS seja a causa; as chamadas da extensão têm host permission explícita. Não foram alterados CORS ou permissões.

Defeitos de código confirmados e corrigidos:

1. O worker retornava por security latch antes de processar Dev Control. A manutenção local agora continua disponível, enquanto leitores e claims de conteúdo continuam bloqueados.
2. Bootstrap só era considerado quando faltava build ID, mesmo com heartbeat antigo. Agora considera desconexão e só usa a página local da Companion se o perfil dedicado já estiver em execução; recusa criar outro Chrome.
3. Reload reutilizava a URL atual sem excluir o vídeo conhecido com 403. Reload normal agora preserva o latch sem navegação e mantém URLs falhadas fora dos defaults mesmo após clearance. Pedido explícito de abertura usa aba elegível ou home, nunca a URL conhecida como falhada.
4. “Following/Profile/Messages” no texto da página confirmava indevidamente authenticated_hint. Foi substituído por controles visíveis de navegação da própria conta com avatar e inbox, sem controles visíveis de login, documento completo e página saudável. Ausência desses elementos mantém sessão unconfirmed. O backend também rejeita confirmação sem essa evidência.
5. O adapter do runner consultava `page_signals.page_ready_state`, mas o backend publica `ready_state`. Contrato corrigido e coberto por teste. O runner exige sessão confirmada e página saudável.

Tentativa real pelo mecanismo autorizado:

```text
scripts/devctl.py reload-extension
ERROR: Dedicated Chrome profile is not running; refusing to open another Chrome.
Restore the existing Companion profile first
```

O mecanismo parou antes de abrir janela, navegar ou criar comando de conteúdo. Nenhum retry loop. Após essa falha houve somente verificação local, testes, documentação e reinício do backend.

## CURRENT URL / SESSION STATUS / SECURITY STOP

| Estado | Resultado atual |
|---|---|
| companion_connected | false |
| heartbeat_fresh | false |
| current_url | última reportada: https://www.tiktok.com/@vitrineglei/video/7673992589036506388 |
| current_page_status | unknown — heartbeat antigo não comprova página atual |
| tiktok_session_status | unconfirmed |
| security_stop | active, preservado |
| failed_url | https://www.tiktok.com/@vitrineglei/video/7673992589036506388 |

Stop original: `HTTP 403`, observado em **2026-10-22T12:25:59.604Z**. Não houve novo 403 observado nesta execução. O incidente antigo não foi apagado nem convertido em prova de indisponibilidade global do TikTok.

O fluxo implementado separa reload da validação explícita da home. `devctl.py validate-home` navega uma aba existente uma única vez para `https://www.tiktok.com/`, sem search, sem alterar cookies e sem limpar latch. Requer duas amostras elegíveis da home; challenge/login/novo incidente interrompem. Resultado incerto de navegação não é repetido.

`clear-reviewed-stop --validation-id ID` só aceita comando de validação concluído, build/extension ID corretos, home completa/autenticada com heartbeat de menos de 15 segundos e incidente inalterado. Arquiva incidente/failed_url antes de limpar; o worker só remove o mesmo incidente, sem descartar um novo 403. Nenhum desses dois comandos foi executado na sessão real desconectada. A condição `isolated_403` permanece **não confirmada em produção** até home saudável.

A tela Conexão mostra separadamente Companion, heartbeat, sessão, página atual, security stop e failed URL. Sem redesign geral. A confirmação DOM é conservadora e ainda precisa de validação real; seletores ausentes deixam sessão não confirmada.

## SMOKE TEST

| Etapa | Resultado |
|---|---|
| SEARCH | Não executado: pré-condições de conexão/home/sessão ausentes |
| VIDEO DETAIL | Não executado |
| COMMENT SAMPLE | Não executado |
| CREATOR PROFILE | Não executado |
| Resultado | Bloqueado antes de qualquer comando TikTok |

## DISCOVERY STATUS

Sessões novas: **0**. Queries executadas: **nenhuma**. Vídeos vistos/novos/duplicados/creators desta execução: **0 / 0 / 0 / 0**. Candidates e unresolved da nova coleta: **não medidos**. Novelty, duplicate e candidate rate da execução: **N/A**, sem denominador.

Pipeline SAVE → DEDUP → CLASSIFY → DETECTOR → METRICS não iniciado. Limites preservados: 3 sessões, 20 novos por sessão, 50 novos totais. Nenhum runner/backlog iniciado. Os defaults do runner existente são mais amplos; não devem ser usados sem os limites específicos desta missão.

## CATEGORIES / PRESERVATION

| Indicador | Antes | Depois |
|---|---:|---:|
| Vídeos na Library | 45 | 45 |
| Casa | 8 | 8 |
| Eletrônicos | 1 | 1 |
| Classified | 9 | 9 |
| Ambiguous | 0 | 0 |
| Unclassified | 36 | 36 |
| Candidates | 8 | 8 |
| Evidências de candidates | 65 | 65 |
| Unresolved phrases | 2 | 2 |

Não há amostra nova de 5 classified/5 unclassified. Caption, candidate, category, subcategory, product_family, category evidence e source query dos novos vídeos não foram avaliados. Não se substituiu essa validação por uma amostra histórica apresentada como nova.

Backup anterior: `checkpoint-20261023T150103Z.db`; hashes/tabelas/fontes em `checkpoint.json`. Auditoria final em `after.json`: integrity_check **ok**, foreign_key_check vazio. Somente dev_commands (coluna aditiva options_json), events, sqlite_sequence e system_state diferem. Todas as tabelas preexistentes de negócio, Gold Set, benchmark, candidates/evidence, resolver, classificações, enrichment e bridge_commands mantêm os hashes anteriores. Security stop original intacto. Taxonomy, classifier, planner, detector e seus configs preservados. Perfil Chrome e histórico de queries preservados.

## QUERY PERFORMANCE / PLANNER

Somente histórico persistido, sem buscas novas: `home gadgets` possui 7 sessões, 68 vistos por sessão somados, 28 novos e 40 duplicados conhecidos. Novelty **41,18%**, duplicate **58,82%**; 29 creators e 8 vídeos com candidates entre 45 vídeos atribuídos à query (candidate rate **17,78%**). As 71 aparições duplicadas brutas de viewport são outra métrica, não o denominador dessas taxas. Duas unresolved phrases globais pertencem a um vídeo atribuído; unresolved_count por query conta vídeos, não frases.

Melhor novelty e maior duplicate rate históricos: `home gadgets`, única query com sessões. Não há comparação empírica suficiente entre queries.

Planner offline, sem gravar histórico nem executar queries:

1. **home organization**: base 10, novelty 0 sem observações, duplicate penalty 0, creators 0, age 2, underrepresented 2. Histórico: nenhuma execução; taxas null.
2. Excluindo a primeira: **home gadgets**. Histórico conhecido acima; há penalidade por duplicação, bônus por novelty/creators e idade.
3. Excluindo as duas: **useful home products**, sem execução anterior.

O código e os testes preservam cooldown/exclusões, métricas com denominadores corretos e componentes explícitos de novelty, duplicação, creators e categorias pouco exploradas. A seleção não ficou presa na mesma query no ensaio offline. A qualidade das decisões em novas sessões reais permanece pendente. Não foi alterado o planner.

## ENRICHMENT PRIORITY

Auditoria somente leitura dos 45 vídeos: todos os scores conferem com os pesos/configuração e motivos retornados. Favorece categoria conhecida, candidate ausente, caption com menos de três palavras, unresolved, thumbnail e buying terms nos comentários. Há também bônus por comments_available.

Limites: não há flag independente de provável produto; categoria/unresolved são contexto indireto. Caption genérica com três ou mais palavras não é necessariamente considerada insuficiente; sinais comerciais são os termos já disponíveis nos comentários. Essas limitações foram registradas, sem adicionar detector, scoring novo ou executar backlog.

## VISUAL QUEUE

`visual-identification-queue.json`: **2 candidatos históricos** para revisão futura; não são novos produtos confirmados. Critério local explícito: candidate ausente AND thumbnail disponível AND (categoria conhecida OR unresolved).

- Library 42: candidate ausente, thumbnail, categoria conhecida, comentários insuficientes.
- Library 1: candidate ausente, thumbnail, categoria conhecida, unresolved phrase.

URLs de imagens não foram acessadas nem verificadas; thumbnail disponível significa referência persistida. Não houve Lens, provider visual, download externo ou gravação de VisualProductEvidence/labels.

## TESTS

- **252 Python passed**, 4 avisos de depreciação existentes. Task `ae3d5a417f954a768b4a9a2b33d51f9a` SUCCEEDED, exit_code 0.
- **113 Node/dashboard passed**, zero failures/skips. Task `6a458265604640febc0da5d6ccd7c2ba` SUCCEEDED, exit_code 0.
- Logs completos em `.runtime/logs/task-ID.json` e `.log`.
- Inclui regressão de categorias, runner/checkpoints, segurança, Companion, payload de heartbeat e dashboard. Novos testes cobrem identidade da conta, rejeição de texto genérico/login/challenge, reload sob latch, home única, incidente alterado, clearance condicionado, replay antigo, bootstrap sem segundo Chrome e readiness real do adapter.
- `git diff --check` passou; avisos CRLF referem-se a arquivos preexistentes. Nenhuma cobertura removida. A expectativa antiga de autenticação por texto genérico foi substituída por rejeição explícita e testes de evidência positiva/negativa.

## STOP REASON / NEXT RECOMMENDED SPRINT

**Companion impossível de reconectar no estado atual sem abrir outro perfil/janela Chrome**, o que foi recusado. A validação completa não está concluída. Este relatório não representa um smoke/discovery bem-sucedido.

Próximo passo necessário: disponibilizar legitimamente o perfil existente que contém a Companion, preservando login/cookies. Depois usar Dev Control, validar apenas home, conferir sessão/incident history e só então liberar o stop antigo se elegível. Executar exatamente um smoke SEARCH/detail/comments/creator antes de até 3 sessões dentro de 20 novos/sessão e 50 novos totais. Nenhum sprint de Supplier/Opportunity/Lens/Resolver avançado iniciado.

Evidências adicionais: `profile-registration.json`, `connection-before.json`, `after.json`, `visual-identification-queue.json`; `audit.py` é exportador somente leitura. Nenhum Computer Use utilizado nesta continuação; nenhum engagement, bypass, spoofing, cookie/login change, commit ou staging.
