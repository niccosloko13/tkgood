# BABI V1 EXECUTION PLAN

## PARTE 1 — CONSOLIDAÇÃO, LIMPEZA E ARQUITETURA FINAL

### 1. MISSÃO

A missão da Babi v1 é:

**identificar produtos que estejam começando a ganhar força, acompanhar sua evolução ao longo do tempo e explicar claramente por que eles merecem atenção.**

A pergunta principal que a Babi precisa responder é:

> **O que está começando a crescer agora e por que vale investigar para vender?**

Toda alteração futura deve contribuir diretamente para pelo menos um destes objetivos:

- melhorar descoberta;
- melhorar evidência temporal;
- melhorar ranking/priorização;
- melhorar explicabilidade;
- melhorar confiabilidade do collector search-only.

Se uma alteração não contribuir para nenhum desses objetivos, ela deve ser adiada.

---

## 2. PRINCÍPIO DE ARQUITETURA

A Babi não será reconstruída.

A arquitetura atual será consolidada.

O sistema deverá evoluir para este caminho principal:

```text
COMPANION / BROWSER
        ↓
    SAFETY GATE
        ↓
 DISCOVERY RUNNER
        ↓
   OBSERVATIONS
        ↓
 TREND SNAPSHOTS
        ↓
   TREND ENGINE
        ↓
CANDIDATE RANKING
        ↓
TOP OPPORTUNITIES
        ↓
       WHY
```

Recursos avançados permanecem separados:

```text
VISUAL / IDENTITY
OpenCLIP
FAISS
Visual Search
Gold Set
Direct Enrichment
Supplier Intelligence
```

Esses recursos não devem bloquear o fluxo principal da Babi v1.

---

## 3. REFERÊNCIAS DE ARQUITETURA

A Babi deve aproveitar conceitos de projetos maduros sem incorporar frameworks grandes desnecessariamente.

### Crawlee

Referência para:

- lifecycle centralizado;
- request/work queue;
- bounded work;
- armazenamento separado da execução;
- deduplicação;
- controle de execução.

Não copiar:

- proxy rotation;
- fingerprint spoofing;
- evasão;
- retries contra bloqueios.

Conceito aproveitado:

```text
um runner controla o ciclo inteiro
em vez de múltiplos scripts controlarem partes do mesmo ciclo
```

### Temporal

Referência conceitual para:

```text
RUN
↓
CHECKPOINT
↓
STATE
↓
RESULT
↓
STOP REASON
↓
RESUME
```

Não instalar Temporal.

SQLite já é suficiente para persistir os estados necessários da Babi v1.

O objetivo é copiar a ideia de workflow durável e idempotente.

### River

Referência para a futura inteligência temporal.

A Babi recebe observações sequenciais.

Portanto deve pensar em:

```text
observation t1
observation t2
observation t3
...
```

e não apenas em datasets estáticos.

Primeiro implementaremos métricas matemáticas simples.

River deverá ser considerado posteriormente para:

- estatísticas online;
- drift detection;
- anomaly detection;
- progressive validation;
- modelos incrementais.

### ruptures

Será considerado somente quando existirem séries suficientemente longas.

Objetivo futuro:

detectar mudança real de regime.

Exemplo:

```text
crescimento normal
crescimento normal
crescimento normal
↓
mudança brusca
↓
BREAKOUT
```

Não faz parte do caminho crítico atual.

### FAISS / OpenCLIP

Continuam úteis para identidade e similaridade visual.

Entretanto:

**não fazem parte do Discovery Loop principal.**

A execução pesada de Torch/OpenCLIP deverá permanecer opcional.

---

## 4. ESTADO REAL DO PROJETO

A auditoria encontrou aproximadamente:

```text
Projeto total: ~5 GB

Core de código:
~2 MB

Principais consumidores:

.venv
browser profile
OpenCLIP model
runtime
artifacts/checkpoints
```

Portanto existem dois problemas diferentes:

### Complexidade lógica

Resolver através de:

- consolidação;
- interfaces canônicas;
- menos runners;
- menos caminhos paralelos.

### Peso em disco

Resolver através de:

- limpeza de cache;
- separação de dependências;
- retenção de artifacts;
- runtime housekeeping.

Não confundir os dois problemas.

---

## 5. POLÍTICA DE LIMPEZA

A limpeza será executada em camadas.

Nada importante será apagado apenas porque parece antigo.

### CLEANUP LEVEL A — SAFE

Pode ser removido depois de parar os processos relevantes:

- `__pycache__`;
- `.pytest_cache`;
- caches Python regeneráveis;
- caches de testes claramente isolados;
- outputs temporários comprovadamente regeneráveis.

A auditoria já identificou aproximadamente:

```text
94.57 MiB
7.211 arquivos
```

classificados como SAFE TO DELETE.

Esses arquivos não contêm dados autoritativos.

---

## 6. CLEANUP LEVEL B — TEST ENVIRONMENT

Existem aproximadamente:

```text
117 MiB
```

em perfis isolados de testes de UI classificados como provavelmente seguros.

Antes de remover:

1. confirmar que nenhum Chrome usa os perfis;
2. confirmar que não são o profile principal;
3. preservar qualquer relatório útil;
4. remover somente os profiles de teste.

Nunca remover:

```text
browser-profiles/chrome-tiktok-main
```

sem uma migração explícita.

Esse profile contém estado necessário para a sessão usada pela Babi.

---

## 7. CLEANUP LEVEL C — ARTIFACT RETENTION

A pasta `artifacts/` contém dezenas de MB de:

- checkpoint DBs;
- relatórios de sprints;
- before/after;
- validações históricas.

Não apagar tudo.

Criar política:

```text
artifacts/
    current/
    archive/
```

`current/`:

- relatórios ativos;
- último checkpoint relevante;
- documentação atual.

`archive/`:

- sprints concluídos;
- checkpoints antigos;
- relatórios históricos.

Depois de validar que os checkpoints antigos não são necessários para rollback:

eles podem ser compactados ou removidos mediante aprovação.

---

## 8. NÃO APAGAR

Nesta fase é proibido apagar:

```text
data/product_hunter.db
browser-profiles/chrome-tiktok-main
Gold Set
security incident history
source provenance
trend history
search observations
source links
signing keys
cookies/session profile
```

Também não apagar manualmente arquivos internos de:

```text
.venv
torch
open_clip
faiss
```

Se dependências forem removidas, deverá ser feito recriando o ambiente corretamente.

---

## 9. SEPARAÇÃO DO AMBIENTE

O projeto atual carrega dependências muito pesadas para recursos que não fazem parte do fluxo search-only.

Objetivo futuro:

```text
requirements-core.txt
```

contendo somente o necessário para:

- FastAPI;
- SQLite;
- Companion;
- collector;
- trend;
- dashboard.

E:

```text
requirements-intelligence.txt
```

contendo:

- Torch;
- OpenCLIP;
- FAISS;
- dependências visuais.

Não remover essas dependências hoje.

Primeiro comprovar a separação.

Depois poderá ser criado um ambiente core muito mais leve.

---

## 10. CÓDIGO POSSIVELMENTE LEGADO

A auditoria encontrou alguns scripts sem consumidores estáticos conhecidos:

```text
local_visual_assets_report.py
offline_intelligence_report.py
report_intelligence_core.py
validate_connection_panel.py
```

Eles NÃO devem ser apagados imediatamente.

Primeiro:

```text
verificar chamadas
↓
verificar testes
↓
verificar documentação
↓
verificar CLI/manual usage
```

Se não houver dependência:

mover para:

```text
tools/legacy/
```

Executar toda a regressão.

Somente depois considerar exclusão.

---

## 11. REGRA PARA REMOÇÃO

Nenhum código será apagado apenas porque:

- é antigo;
- não aparece no dashboard;
- não possui import direto;
- parece duplicado.

Para remover um componente é necessário comprovar:

```text
0 production callers
0 required tests
0 required migrations
0 required historical compatibility
replacement validated
full regression green
```

---

## 12. CONSOLIDAÇÃO DE EXECUÇÃO

A auditoria mostrou repetição de orchestration entre Stage 1 e Stage 2.

Isso deve desaparecer conceitualmente.

Criar uma única fachada:

```text
DiscoveryRunner
```

Configuração aproximada:

```text
queries
max_results_per_query
max_new_videos
max_runtime
search_only
```

Então:

```text
Stage 1
```

deixa de ser uma arquitetura.

Passa a ser apenas:

```text
DiscoveryRunner(
    queries=1,
    max_results_per_query=10
)
```

E Stage 2:

```text
DiscoveryRunner(
    queries=5,
    max_new_videos=30
)
```

Um runner.

Uma política.

Um formato de relatório.

Um lifecycle.

---

## 13. NÃO APAGAR STAGE 1/2 IMEDIATAMENTE

Primeiro criar o runner canônico.

Depois adaptar Stage 1/2 antigos para chamarem o novo runner.

Fluxo:

```text
legacy Stage1 ─┐
               ├── DiscoveryRunner
legacy Stage2 ─┘
```

Rodar regressão.

Quando comprovado:

```text
Stage1/Stage2 legacy
→ DEPRECATED
```

Depois remover.

Isso impede uma refatoração destrutiva.

---

## 14. SAFETY GATE CANÔNICO

Hoje há sinais de challenge e sessão em múltiplas camadas.

Preservar a proteção existente, mas definir uma fonte conceitual única.

Estados de página:

```text
HEALTHY
LOADING
CHALLENGE
LOGGED_OUT
ERROR
UNKNOWN
```

Estados de segurança:

```text
OK
TARGET_BLOCKED
GLOBAL_BLOCKED
```

O collector consulta Safety.

Safety não calcula:

- trend;
- candidate priority;
- lifecycle;
- opportunity.

Ela só responde:

> Pode continuar?

---

## 15. SCOPE FREEZE

Durante esta consolidação NÃO implementar:

- Stage 3;
- Stage 4;
- novo recovery;
- novo detector de sessão;
- novo score global;
- comments enrichment;
- creator enrichment;
- direct video enrichment;
- supplier search;
- Lens automático;
- novo modelo ML;
- BERTopic;
- ruptures em produção;
- Temporal;
- Crawlee.

O objetivo é reduzir, não aumentar.

---

## 16. DEFINITION OF DONE — PARTE 1

Esta fase termina quando:

```text
✓ caches seguros identificados/limpos

✓ profiles de teste revisados

✓ artifacts têm política de retenção

✓ código suspeito está classificado

✓ nenhum dado importante foi perdido

✓ DiscoveryRunner é o caminho canônico

✓ Stage1/Stage2 usam o mesmo runner

✓ Safety possui contrato único

✓ nenhuma regressão funcional

✓ search-only continua funcionando

✓ testes Python verdes

✓ testes JavaScript verdes
```

Somente depois disso começa:

# PARTE 2 — DISCOVERY LOOP + TREND ENGINE V2