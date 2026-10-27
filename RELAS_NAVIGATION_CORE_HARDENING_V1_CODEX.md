# RELAS — NAVIGATION CORE HARDENING V1
## BUSCA PRECISA + DRIVE SIMULATOR + LATENCY PROFILING + SMOOTHING SEPARADO

### OBJETIVO

Executar uma missão curta, controlada e determinística para melhorar a navegação do RELAS sem ampliar escopo.

Prioridades, nesta ordem:

1. corrigir busca por rua + número;
2. criar Drive Simulator;
3. medir o delay exatamente;
4. separar marker smoothing de camera smoothing;
5. diminuir/adaptar cameraLag;
6. apenas documentar caminho futuro para app nativo — NÃO implementar app nativo nesta missão.

---

# REGRAS DE EXECUÇÃO

Esta missão NÃO pode virar uma sprint aberta.

## Limites

- Não redesignar o produto.
- Não mexer em ARTESP/SIBH/PRF/ANTT.
- Não adicionar comunidade.
- Não adicionar rewards.
- Não implementar iOS/Android.
- Não alterar Official Radar Finder.
- Não alterar banco/schema salvo quando não for estritamente necessário.
- Não fazer deploy.
- Não fazer push.

## Anti-loop

Para cada etapa:

```text
IMPLEMENTAR
→ testar suíte específica
→ corrigir no máximo 2 vezes
→ se continuar falhando, documentar BLOCKED
→ seguir para próxima etapa
```

Não repetir a mesma suíte completa indefinidamente.

A suíte completa deve rodar apenas:

1. baseline;
2. depois de todas as etapas concluídas;
3. uma única vez no final.

Se browser smoke for flakey:
marcar `FLAKY_BROWSER_TEST` e documentar.

---

# 0. CHECKPOINT

Antes de alterar código:

- registrar branch atual;
- registrar HEAD;
- salvar `git status --short`;
- criar checkpoint;
- rodar apenas baseline mínimo relevante.

Artefato:

```text
artifacts/navigation-core-hardening-v1/BASELINE.md
```

Registrar:

```text
search tests
navigation tests
location tests
browser smoke status
current camera animation duration
current marker animation behavior
current geocoder provider(s)
```

---

# 1. CORRIGIR BUSCA RUA + NÚMERO

## Problema comprovado

Consulta como:

```text
Rua Rui Barbosa, 521, Praia Grande
```

não prioriza corretamente:

```text
Rua Rui Barbosa + número 521 + Praia Grande
```

e retorna ruas diferentes contendo apenas o token `Barbosa`.

Também foram observados:

- número ignorado;
- fuzzy match vencendo rua exata;
- duplicatas;
- rótulo “número não localizado” em rua que não corresponde à consulta.

---

# 1.1 PARSER ESTRUTURADO

Criar função explícita:

```text
parseAddressQuery(raw)
```

Retorno conceitual:

```json
{
  "street": "Rua Rui Barbosa",
  "number": "521",
  "city": "Praia Grande",
  "state": null,
  "postal_code": null,
  "raw": "Rua Rui Barbosa, 521, Praia Grande"
}
```

Suportar:

```text
Rua + número
Rua + número + cidade
Rua + número + cidade + UF
CEP
Rua sem número
```

Não depender apenas do split por vírgula.

---

# 1.2 PIPELINE DE BUSCA

Ordem obrigatória:

```text
1 EXACT STREET + NUMBER + CITY
2 EXACT STREET + CITY
3 STREET PREFIX + CITY
4 ADDRESS INTERPOLATION / APPROXIMATE NUMBER
5 FUZZY STREET MATCH
```

Fuzzy match nunca pode vencer match exato de rua+cidade.

Se número não for encontrado:

mostrar primeiro:

```text
Rua Rui Barbosa, próximo ao nº 521
Praia Grande - SP
Número aproximado
```

e só depois sugestões de outras ruas.

---

# 1.3 RANKING

Criar score explicável.

Exemplo:

```text
exact_street       +100
exact_city         +60
exact_number       +80
number_proximity   +0..40
same_postcode      +30
prefix_street      +20
fuzzy_street       +0..15
different_street   penalty
different_city     strong penalty
```

Não precisa usar exatamente esses números, mas precisa documentar a lógica.

---

# 1.4 DEDUPE

Deduplicar resultados por:

```text
normalized street
number
city
postcode
lat/lon proximity
```

Nunca mostrar o mesmo endereço duas vezes.

---

# 1.5 LABEL CORRETO

Estados:

```text
EXACT_ADDRESS
APPROXIMATE_NUMBER
STREET_ONLY
FUZZY_ALTERNATIVE
```

Rótulos:

```text
Número exato
Número aproximado
Rua localizada
Sugestão alternativa
```

Não usar “número não localizado” em uma rua diferente.

---

# 1.6 TESTES OBRIGATÓRIOS

Testar:

```text
Rua Rui Barbosa, 198, Praia Grande
Rua Rui Barbosa, 521, Praia Grande
Rua Rui Barbosa, 818, Praia Grande
Rua Rui Barbosa, 999999, Praia Grande
Barbosa, 521, Praia Grande
Rua Rui Barbosa, Praia Grande
CEP válido
```

Critérios:

- rua exata deve vencer;
- cidade correta deve vencer;
- número exato quando disponível;
- aproximado quando necessário;
- sem duplicatas;
- fuzzy abaixo de exato.

Criar:

```text
SEARCH_ADDRESS_REPORT.md
```

---

# 2. DRIVE SIMULATOR V1

## Objetivo

Criar um simulador determinístico que injete localização simulada no mesmo pipeline usado pela navegação.

Arquitetura:

```text
REAL GPS
    \
     → Location Engine
    /
SIMULATED GPS
```

O resto do sistema não deve precisar saber se o ponto veio do GPS real ou do simulador.

---

# 2.1 ESTRUTURA

Criar algo equivalente a:

```text
scripts/drive-simulator/
  route-loader.js
  gps-generator.js
  scenarios.js
  simulator.js
  report.js
```

Adaptar à arquitetura real do projeto.

---

# 2.2 ROTA

Usar uma rota real já suportada pelo sistema.

Cenários iniciais:

```text
Praia Grande → São Bernardo do Campo
Rua Rui Barbosa 198 → Rua Rui Barbosa 521
```

Não depender de serviço externo instável durante o teste se a rota puder ser cacheada.

Salvar fixtures de rota separadas:

```text
tests/fixtures/drive-simulator/
```

---

# 2.3 PONTO GPS SIMULADO

Cada fix deve conter:

```text
lat
lon
timestamp
speed
heading
accuracy
altitude? optional
```

---

# 2.4 CENÁRIOS

Implementar:

```text
normal
urban
highway
gps-noise
gps-delay
gps-loss
off-route
parallel-road
wrong-direction
stop-and-go
high-speed
```

Cada cenário precisa ser determinístico.

Sem random sem seed.

---

# 2.5 VELOCIDADE DE REPLAY

Suportar:

```text
1x
5x
10x
20x
```

---

# 2.6 SAÍDA

Relatório automático:

```text
route completed
distance
virtual duration
road mode transitions
radar candidates
radars alerted
missed alerts
wrong-direction alerts
late alerts
reroutes
gps losses
gps recoveries
SAU detected
tolls detected
```

Gerar:

```text
DRIVE_SIMULATOR_REPORT.md
```

---

# 3. MEDIR O DELAY EXATAMENTE

## Regra

NÃO alterar smoothing antes de medir.

Instrumentar timestamps separados:

```text
gpsReceivedAt
locationProcessedAt
matchCompletedAt
displayTargetAt
markerRenderedAt
cameraCommandAt
cameraSettledAt
```

Calcular:

```text
gpsAgeMs
locationEngineMs
mapMatchMs
markerLagMs
cameraCommandLagMs
cameraSettleLagMs
endToEndVisualLagMs
```

---

# 3.1 PONTOS DE MEDIÇÃO

Medir em:

```text
urban 30 km/h
urban 50 km/h
highway 80 km/h
highway 100 km/h
gps delay scenario
gps loss recovery
```

---

# 3.2 NÃO CONFUNDIR

Separar:

```text
GPS delay
processing delay
marker smoothing
camera smoothing
map render
```

Não atribuir tudo ao GPS.

---

# 3.3 RELATÓRIO

Criar:

```text
LATENCY_PROFILE.md
```

Tabela:

```text
scenario
speed
gpsAgeMs p50/p95
processing p50/p95
markerLag p50/p95
cameraLag p50/p95
endToEnd p50/p95
```

---

# 4. SEPARAR MARKER SMOOTHING DE CAMERA SMOOTHING

## Estado desejado

Criar conceitos separados:

```text
rawLocation
matchedLocation
displayLocation
cameraTarget
```

### Marker

Responsável por:
- movimento visual do carro;
- interpolação curta;
- correção suave.

### Camera

Responsável por:
- framing;
- look-ahead;
- zoom;
- bearing;
- pitch.

A câmera NÃO deve controlar o atraso do marcador.

---

# 4.1 MARKER LOOP

Marker deve possuir loop próprio de render/interpolation.

Não depender de animação longa da câmera.

---

# 4.2 CAMERA

Camera pode usar:

```text
speed
heading
distance to maneuver
road mode
```

mas sua animação deve ser independente.

---

# 5. CAMERA LAG ADAPTATIVO

Somente após LATENCY_PROFILE.

Remover dependência de duração fixa única se existir.

Estratégia inicial sugerida:

```text
0–20 km/h     250–350 ms
20–60 km/h    150–250 ms
60–100 km/h    80–150 ms
>100 km/h      50–100 ms
```

Esses valores são ponto de partida, não verdade absoluta.

Usar benchmark/simulador para escolher valores.

---

# 5.1 PREDICTION

Preservar regras existentes do Precision Engine.

Não ampliar previsão além das proteções atuais.

Princípio:

```text
prediction curta
correção suave
fallback seguro
```

Não inventar posição para parecer bonito.

---

# 5.2 CAMERA LOOK-AHEAD

Em movimento:

```text
user marker abaixo do centro
mais espaço à frente
menos espaço atrás
```

Look-ahead aumenta com velocidade.

---

# 6. TESTE VISUAL AUTOMATIZADO

Criar smoke visual com Playwright apenas para:

```text
marker motion
camera follow
route progress
CITY_MODE
ROAD_MODE
radar alert card
```

Capturar:

```text
30 km/h
60 km/h
90 km/h
```

Não reexecutar dezenas de vezes.

Máximo:
- 1 execução inicial;
- 1 execução após correção;
- 1 execução final.

---

# 7. GATES DE QUALIDADE

## SEARCH GATE

PASS se:

- endereço exato aparece acima dos fuzzy;
- número influencia ranking;
- duplicatas removidas.

## SIMULATOR GATE

PASS se:

- replay determinístico;
- todos os cenários executam;
- relatório gerado.

## LATENCY GATE

PASS se:

- métricas separadas disponíveis;
- nenhum valor inventado.

## SMOOTHING GATE

PASS se:

- marker e camera separados;
- cameraLag adaptativo;
- sem regressão de map matching.

---

# 8. STOP CONDITIONS

A missão DEVE parar se:

- search provider externo estiver indisponível;
- browser test estiver flakey após 2 tentativas;
- alguma mudança exigir refatoração grande fora do escopo;
- houver risco de quebrar Precision Engine.

Nesses casos:

```text
BLOCKED
```

e documentar.

Não expandir missão.

---

# 9. SUÍTES

Executar:

## baseline
somente testes relevantes.

## durante desenvolvimento
somente suíte da etapa.

## final
uma única rodada:

```text
navigation tests
location tests
search tests
drive simulator tests
browser smoke
selftest
syntax
```

Não rodar full suite repetidamente.

---

# 10. ARTEFATOS

Criar:

```text
artifacts/navigation-core-hardening-v1/BASELINE.md
artifacts/navigation-core-hardening-v1/SEARCH_ADDRESS_REPORT.md
artifacts/navigation-core-hardening-v1/DRIVE_SIMULATOR_REPORT.md
artifacts/navigation-core-hardening-v1/LATENCY_PROFILE.md
artifacts/navigation-core-hardening-v1/SMOOTHING_ARCHITECTURE.md
artifacts/navigation-core-hardening-v1/VISUAL_VALIDATION.md
artifacts/navigation-core-hardening-v1/KNOWN_LIMITATIONS.md
artifacts/navigation-core-hardening-v1/REPORT.md
artifacts/navigation-core-hardening-v1/TEST_RESULTS.json
```

---

# 11. REPORT FINAL

Responder:

1. busca rua+número foi corrigida?
2. Rua Rui Barbosa 198 funciona?
3. Rua Rui Barbosa 521 funciona?
4. Rua Rui Barbosa 818 funciona?
5. número inexistente mantém rua correta?
6. duplicatas foram removidas?
7. Drive Simulator funciona?
8. quais cenários foram executados?
9. markerLag p50/p95?
10. cameraLag p50/p95?
11. endToEndVisualLag p50/p95?
12. marker smoothing está separado da câmera?
13. camera duration virou adaptativa?
14. houve regressão de map matching?
15. radar P0 foi preservado?
16. wrong-direction suppression continua funcionando?
17. GPS-loss recovery continua funcionando?
18. quais limitações permanecem?
19. está pronto para novo teste físico?

---

# 12. APP NATIVO — SOMENTE DOCUMENTAR

Não implementar.

Criar seção final:

```text
NATIVE_APP_NEXT.md
```

Documentar apenas:

- por que PWA limita localização;
- Core Location;
- Fused Location Provider;
- background navigation;
- logs/crash reporting;
- Android Auto / CarPlay;
- migração futura.

Sem criar projeto iOS/Android nesta missão.

---

# PRINCÍPIO FINAL

Primeiro medir.
Depois corrigir.

Não usar animação para esconder erro de localização.

Não usar previsão para fingir precisão.

O objetivo é reduzir atraso visual de forma mensurável e manter o RELAS seguro, determinístico e testável.
