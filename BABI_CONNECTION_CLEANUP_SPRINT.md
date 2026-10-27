Copia e cola isso num arquivo chamado:

`BABI_CONNECTION_CLEANUP_SPRINT.md`

```md
# BABI — CONNECTION CLEANUP SPRINT

## Objetivo

Simplificar profundamente a experiência de conexão da Babi sem enfraquecer a segurança nem reescrever o core.

A meta desta sprint é transformar a conexão atual em um sistema:

- simples para o usuário;
- previsível;
- fácil de diagnosticar;
- robusto internamente;
- com menos estados expostos;
- com menos confusão entre conexão, sessão, segurança e execução;
- com menos componentes duplicados;
- com uma única fonte de verdade operacional.

A arquitetura conceitual deve ser:

```text
PAINEL BABI
   ↓
BACKEND LOCAL
   ↓
EXTENSÃO CHROME
   ↓
CONTENT SCRIPT
   ↓
ABA REAL DO TIKTOK
```

O navegador real continua sendo a fonte da verdade.

A Babi apenas:

```text
observa
coordena
autoriza
registra
```

---

# 1. PRINCÍPIO CENTRAL

## Simples por fora, robusta por dentro

A interface não deve expor diretamente toda a implementação interna.

Estados internos como:

```text
tiktok_tab
heartbeat
PAGE
SESSION
GLOBAL_SECURITY
latch
quarantine
bridge
command_queue
runtime
recovery_state
```

podem continuar existindo.

Mas o usuário normal não precisa interpretar tudo isso.

A interface deve traduzir para estados simples:

```text
CONNECTED
ATTENTION
BLOCKED
DISCONNECTED
```

---

# 2. NÃO RECONSTRUIR O SISTEMA

Esta sprint NÃO deve:

- substituir o Companion;
- remover o Safety Contract;
- remover quarantine;
- remover latch;
- reescrever o DiscoveryRunner;
- mudar regras de search-only;
- reativar Direct Video Enrichment;
- trocar o navegador principal;
- migrar para Selenium;
- migrar para Playwright como browser principal;
- criar stealth;
- criar proxy rotation;
- criar fingerprint spoofing;
- alterar políticas de segurança.

O objetivo é:

```text
CONSOLIDAR
SIMPLIFICAR
LIMPAR
ESCONDER COMPLEXIDADE TÉCNICA
MELHORAR UX
```

---

# 3. ARQUITETURA ALVO DE CONEXÃO

Manter um único fluxo conceitual:

```text
DASHBOARD
   ↓
LOCAL BACKEND
   ↓
COMMAND / STATE BRIDGE
   ↓
CHROME EXTENSION
   ↓
CONTENT SCRIPT
   ↓
TIKTOK REAL
```

O painel nunca deve manipular a página diretamente.

Fluxo correto:

```text
UI
↓
backend
↓
command queue
↓
extension
↓
content script
↓
TikTok
↓
resultado
↓
backend
↓
UI
```

---

# 4. CHROME REAL COMO FONTE DA VERDADE

A Babi deve operar sobre:

- Chrome normal;
- perfil persistente;
- sessão real;
- cookies reais;
- localStorage;
- IndexedDB;
- login persistente;
- 2FA manual;
- CAPTCHA manual.

Não mostrar estados falsos.

Nunca considerar uma ação concluída apenas porque:

- o backend enviou comando;
- o HTTP retornou 200;
- houve clique;
- a fila aceitou a operação.

Sempre que aplicável, confirmar pelo estado real da sessão.

---

# 5. TELA DE CONEXÃO — NOVO MODELO

A tela principal de conexão deve ficar simples.

Exemplo:

```text
CONEXÃO

TikTok
● Conectado

Sessão
● Logada

Navegador
● Ativo

Segurança
● Normal

Modo atual
Search-only

Última comunicação
há 2s
```

Não obrigar o usuário a interpretar:

```text
PAGE=HEALTHY
SESSION=CONFIRMED
TIKTOK_TAB=true
GLOBAL_SECURITY=OK
```

Esses estados continuam internamente.

---

# 6. ESTADOS DE CONEXÃO PARA O USUÁRIO

## CONNECTED

Quando:

- extensão/Companion respondendo;
- heartbeat recente;
- aba do TikTok encontrada;
- sessão confirmada;
- página saudável;
- global security OK.

Mostrar:

```text
Conectado
Tudo pronto para usar.
```

---

## ATTENTION

Problema recuperável sem bloqueio de segurança.

Exemplos:

- TikTok não aberto;
- aba não encontrada;
- página carregando;
- sessão ainda não confirmada;
- estado temporariamente incompleto.

Exemplo:

```text
Atenção
Abra o TikTok no navegador conectado.
```

ou:

```text
Atenção
Aguardando confirmação da sessão.
```

---

## BLOCKED

Quando houver:

- challenge;
- CAPTCHA;
- verify human;
- 403 global;
- latch ativo;
- global blocked.

Mostrar:

```text
Bloqueado por segurança

A Babi interrompeu a operação para proteger a sessão.

Resolva o bloqueio manualmente no navegador.
```

---

## DISCONNECTED

Quando:

- extensão/Companion offline;
- heartbeat expirado;
- browser não responde;
- comunicação local caiu.

Mostrar:

```text
Desconectado

Não foi possível comunicar com o navegador.
```

---

# 7. DIAGNÓSTICO AVANÇADO

Mover todos os detalhes técnicos para:

```text
Conexão
└── Diagnóstico avançado
```

Exibir ali:

```text
Companion online
Extension connected
TikTok tab
Current URL
Heartbeat age
PAGE
SESSION
GLOBAL SECURITY
Latch
Quarantine
Last command
Command status
Last result
Bridge errors
Runtime state
Last recovery event
```

Essa área é para desenvolvimento/suporte.

Não deve dominar a interface principal.

---

# 8. HEARTBEAT

Simplificar completamente.

Regra:

```text
heartbeat recente
→ conectado

heartbeat expirado
→ desconectado
```

Não mostrar cada heartbeat no log principal.

Eventos detalhados de heartbeat devem ficar apenas no diagnóstico técnico.

---

# 9. COMMAND QUEUE CANÔNICA

Auditar se há múltiplos caminhos executando comandos.

Objetivo:

ter uma única interface canônica para:

```text
SEND COMMAND
WAIT RESULT
CONFIRM RESULT
FAIL / TIMEOUT
```

Cada comando deve possuir:

```text
command_id
type
created_at
started_at
finished_at
timeout
status
result
error
```

Estados:

```text
IDLE
PENDING
RUNNING
DONE
FAILED
CANCELLED
```

---

# 10. NÃO PERMITIR COMANDOS DUPLICADOS

Se já existir:

```text
SEARCH
status=RUNNING
```

não iniciar outro SEARCH igual.

Aplicar o mesmo princípio para:

- passive check;
- capture;
- refresh;
- state read;
- recovery action.

Registrar internamente:

```text
IGNORED_DUPLICATE_COMMAND
```

Sem poluir a interface.

---

# 11. CONFIRMAÇÃO PÓS-AÇÃO

Toda ação importante deve seguir:

```text
estado anterior
↓
executar comando
↓
aguardar atualização
↓
ler estado real
↓
confirmar
```

Nunca marcar sucesso somente porque um clique ou comando foi enviado.

---

# 12. LOG OPERACIONAL VS LOG TÉCNICO

Separar rigorosamente.

## LOG OPERACIONAL

Pode aparecer para o usuário:

```text
TikTok conectado
Sessão confirmada
Busca iniciada
24 resultados encontrados
2 novos vídeos
22 duplicados
Busca concluída
Operação interrompida por segurança
```

## LOG TÉCNICO

Mover para diagnóstico:

```text
HEARTBEAT
COMMAND_RECEIVED
BRIDGE_RESULT
DOM_CHANGED
SERVICE_WORKER_WAKE
SESSION_SIGNAL_CHANGED
PAGE_SIGNAL_CHANGED
LATCH_STATE_CHANGED
```

A Babi não pode parecer um console de desenvolvimento.

---

# 13. MENSAGENS DE ERRO

Evitar:

```text
ERROR
UNKNOWN
FAILED
```

Preferir mensagens humanas.

Exemplo:

```text
TikTok não encontrado

Abra o TikTok no navegador conectado e tente novamente.
```

Outro exemplo:

```text
Sessão não confirmada

Faça login manualmente no TikTok.
```

Outro:

```text
Operação bloqueada por segurança

Foi detectado um challenge.
Resolva manualmente antes de continuar.
```

No diagnóstico técnico, mostrar detalhes completos.

---

# 14. LATCH E QUARANTINE

Manter os mecanismos.

Mas esconder complexidade da interface principal.

Interface normal:

```text
Segurança
● Normal
```

ou:

```text
Segurança
● Bloqueada
```

Detalhes técnicos:

```text
GLOBAL LATCH
TARGET QUARANTINE
LAST SECURITY EVENT
RELEASE HISTORY
```

Não remover histórico.

Não liberar latch automaticamente.

---

# 15. RECOVERY

Não criar outro sistema de recovery.

Apenas simplificar a experiência atual.

Fluxo para usuário:

```text
Bloqueio detectado
↓
Abra o TikTok
↓
Resolva CAPTCHA/challenge manualmente
↓
Clique "Reverificar"
↓
Passive check
↓
Conexão restaurada
```

Internamente preservar:

- incident history;
- quarantine;
- latch audit;
- Safety Contract.

---

# 16. BOTÕES DA TELA DE CONEXÃO

A tela normal deve ter poucas ações.

Recomendado:

```text
[ Reverificar conexão ]
[ Abrir TikTok ]
[ Ver diagnóstico ]
```

Opcionalmente:

```text
[ Reiniciar conexão ]
```

somente se já existir de forma segura.

Não mostrar ao usuário comum:

- release latch;
- force state;
- reset security;
- comandos internos;
- IDs;
- debug actions.

---

# 17. ABRIR TIKTOK

Se houver botão:

```text
Abrir TikTok
```

ele deve abrir ou focar a sessão correta.

Não criar outro navegador.

Não criar profile temporário.

Usar o profile persistente autorizado.

---

# 18. STATUS GLOBAL NO HEADER

Mostrar somente resumo simples.

Estado saudável:

```text
● Babi conectada

TikTok OK
Search-only
Segurança normal
```

Estado de atenção:

```text
● Atenção necessária

TikTok não encontrado
```

Estado bloqueado:

```text
● Operação bloqueada

Resolver challenge no navegador
```

---

# 19. "COMPANION" NÃO DEVE SER CONCEITO PRINCIPAL

O termo Companion pode continuar internamente.

Para o usuário, preferir:

```text
Navegador
Chrome conectado
Conexão com navegador
```

Companion pode aparecer somente no diagnóstico avançado.

O usuário não deve precisar entender o que é um Companion para usar a Babi.

---

# 20. AUDITORIA DE COMPONENTES INÚTEIS

Antes de remover qualquer coisa, auditar:

- componentes da tela de conexão;
- endpoints de conexão;
- estados duplicados;
- polling duplicado;
- heartbeat duplicado;
- logs repetidos;
- recovery controls;
- health cards;
- status badges;
- command panels;
- debug panels.

Classificar cada item como:

```text
KEEP
MERGE
MOVE_TO_DIAGNOSTICS
DEPRECATE
REMOVE_AFTER_VALIDATION
```

Não apagar na primeira passagem.

---

# 21. DETECTAR RESPONSABILIDADES DUPLICADAS

Investigar especialmente:

```text
session detection
page health
browser safety
global latch
target quarantine
heartbeat
connection state
command state
recovery state
```

Para cada item perguntar:

> Existe mais de um módulo tentando responder a mesma coisa?

Se sim:

```text
definir fonte canônica
↓
criar adapter para legado
↓
preservar compatibilidade
↓
testar
↓
deprecar antigo
```

---

# 22. ESTADO CANÔNICO DE CONEXÃO

Criar um read model específico para a UI.

Exemplo:

```json
{
  "status": "CONNECTED",
  "message": "Tudo pronto para usar.",
  "browser": "ONLINE",
  "tiktok": "CONNECTED",
  "session": "CONFIRMED",
  "security": "OK",
  "mode": "SEARCH_ONLY",
  "lastSeenSeconds": 2
}
```

A interface deve consumir preferencialmente esse estado.

Detalhes técnicos ficam separados.

---

# 23. NÃO MISTURAR CONEXÃO COM INTELIGÊNCIA

A página de conexão NÃO deve mostrar:

- Top Opportunities;
- lifecycle;
- momentum;
- candidates;
- product quality;
- backtest;
- query performance.

Conexão responde somente:

> A Babi está pronta para operar?

---

# 24. NÃO MISTURAR CONEXÃO COM COLETA

Separar:

## CONEXÃO

```text
está conectado?
está logado?
está saudável?
está seguro?
```

## COLETA

```text
qual query?
running?
quantos resultados?
quantos novos?
quantos duplicados?
finished?
```

---

# 25. NÃO MISTURAR CONEXÃO COM RECOVERY

Recovery só deve aparecer quando houver problema.

Estado normal:

não mostrar recovery.

Estado bloqueado:

```text
[ Resolver no navegador ]
[ Reverificar ]
```

Detalhes de recovery ficam no diagnóstico.

---

# 26. PROFILE PERSISTENTE

Preservar o profile persistente atual.

Exemplo:

```text
browser-profiles/chrome-tiktok-main
```

Não excluir.

Não recriar.

Não mover desnecessariamente.

Não quebrar a sessão existente.

---

# 27. LOGIN MANUAL

Login continua manual.

A Babi:

- não armazena senha;
- não digita senha;
- não resolve 2FA;
- não resolve CAPTCHA;
- não contorna challenge.

Fluxo:

```text
usuário abre TikTok
↓
faz login
↓
resolve 2FA/CAPTCHA
↓
Babi detecta sessão
↓
status = conectado
```

---

# 28. DIRECT VIDEO ENRICHMENT

Continuar:

```text
PAUSED
```

Não alterar nesta sprint.

---

# 29. SEARCH-ONLY

Search-only continua sendo o único modo ativo de coleta.

A página apenas informa:

```text
Modo atual
Search-only
```

Não mostrar todas as regras internas na interface principal.

---

# 30. TESTES OBRIGATÓRIOS

## Conexão normal

```text
Chrome aberto
TikTok aberto
sessão logada
→ CONNECTED
```

## TikTok fechado

```text
Chrome aberto
TikTok fechado
→ ATTENTION
```

## Extensão/Companion offline

```text
sem heartbeat
→ DISCONNECTED
```

## Sessão deslogada

```text
TikTok aberto
sessão não confirmada
→ ATTENTION
```

## Challenge

```text
challenge detectado
→ BLOCKED
```

## Recovery

```text
challenge resolvido manualmente
passive check saudável
release autorizado
→ CONNECTED
```

## Comando duplicado

```text
SEARCH já RUNNING
novo SEARCH igual
→ não iniciar segundo comando
```

## False success

Garantir que a UI não mostre sucesso sem confirmação real.

---

# 31. TESTE VISUAL

Validar como usuário comum.

Perguntas:

```text
Eu sei se a Babi está conectada?

Eu sei se existe algum problema?

Eu sei o que preciso fazer?

Eu consigo entender o erro sem conhecer nomes técnicos?

Eu consigo abrir diagnóstico se precisar?
```

Se qualquer resposta for NÃO, simplificar novamente.

---

# 32. DESIGN DA TELA DE CONEXÃO

Direção:

- limpa;
- moderna;
- poucos cards;
- status claros;
- linguagem humana;
- sem excesso técnico;
- ações evidentes;
- diagnóstico recolhido por padrão.

Exemplo:

```text
┌─────────────────────────────────────┐
│ Conexão                             │
│ Tudo pronto para usar               │
│                                     │
│ ● TikTok conectado                  │
│ ● Sessão logada                     │
│ ● Navegador ativo                   │
│ ● Segurança normal                  │
│                                     │
│ Modo: Search-only                   │
│ Última comunicação: agora           │
│                                     │
│ [ Reverificar ] [ Abrir TikTok ]    │
│                                     │
│ Diagnóstico avançado ▾              │
└─────────────────────────────────────┘
```

---

# 33. AUDITORIA ANTES DA REFATORAÇÃO

Antes de alterações destrutivas, gerar:

```text
artifacts/connection-cleanup/AUDIT.md
```

Incluir:

- componentes atuais;
- endpoints;
- estados;
- polling;
- heartbeat;
- command paths;
- recovery paths;
- duplicações;
- itens inúteis para UI;
- itens que devem permanecer internos;
- riscos de remoção.

---

# 34. RELATÓRIO FINAL

Criar:

```text
artifacts/connection-cleanup/REPORT.md
```

Incluir:

- arquivos alterados;
- componentes removidos da UI;
- componentes movidos para diagnóstico;
- componentes consolidados;
- endpoints preservados;
- adapters criados;
- contratos preservados;
- testes;
- regressões;
- screenshots before/after se possível;
- pendências.

---

# 35. REGRA DE REMOÇÃO

Não apagar módulos diretamente.

Fluxo obrigatório:

```text
AUDIT
↓
CANONICAL INTERFACE
↓
ADAPTER
↓
REGRESSION
↓
DEPRECATE
↓
REMOVE LATER
```

Só remover quando houver:

```text
0 production callers
0 required tests
0 migration dependency
0 recovery dependency
0 safety dependency
replacement validated
regression green
```

---

# 36. DEFINITION OF DONE

A sprint só termina quando:

```text
✓ usuário vê um único estado principal de conexão

✓ mensagens são humanas e acionáveis

✓ detalhes técnicos estão em diagnóstico

✓ Companion não precisa ser entendido pelo usuário

✓ heartbeat não polui a UI

✓ logs técnicos não poluem a UI

✓ conexão, coleta e recovery estão separados

✓ command queue possui estado canônico

✓ comandos duplicados são bloqueados

✓ ações possuem confirmação real

✓ Safety Contract permanece intacto

✓ latch permanece intacto

✓ quarantine permanece intacta

✓ Direct Video Enrichment permanece PAUSED

✓ search-only permanece funcional

✓ profile persistente preservado

✓ histórico de segurança preservado

✓ testes Python verdes

✓ testes JavaScript verdes

✓ nenhuma regressão funcional
```

---

# 37. RESULTADO ESPERADO

ANTES:

```text
Companion
TikTok tab
Heartbeat
PAGE
SESSION
GLOBAL SECURITY
Latch
Quarantine
Recovery
Bridge
Commands
Runtime
```

DEPOIS:

```text
CONEXÃO

● Conectado

TikTok: OK
Sessão: Logada
Navegador: Ativo
Segurança: Normal
Modo: Search-only

[ Reverificar ]
[ Abrir TikTok ]

Diagnóstico avançado ▾
```

A complexidade não desaparece.

Ela deixa de ser problema do usuário.

---

# 38. INSTRUÇÃO FINAL AO CODEX

Execute esta sprint como uma limpeza e consolidação da conexão da Babi.

Ordem:

1. auditar implementação atual;
2. identificar duplicações;
3. definir estado canônico de conexão;
4. simplificar a UI;
5. mover detalhes técnicos para diagnóstico;
6. preservar Safety/latch/quarantine/recovery;
7. preservar profile e sessão;
8. validar command queue e confirmação pós-ação;
9. rodar regressão completa;
10. não fazer commit.

Não adicionar novas features fora deste escopo.

Sem commit.
```