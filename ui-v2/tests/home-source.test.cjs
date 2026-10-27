const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../src/main.tsx'), 'utf8');
const formatters = fs.readFileSync(path.join(__dirname, '../src/lib/formatters.ts'), 'utf8');

test('Home V2 presents pulse, a primary opportunity and safe absence copy in Portuguese', () => {
  assert.match(source, /PULSO DA BABI/);
  assert.match(source, /PRINCIPAL SINAL/);
  assert.match(source, /Detectados hoje/);
  assert.match(source, /Nenhum sinal forte agora/);
  assert.match(source, /slice\(0, 3\)/);
  assert.match(source, /Novas descobertas com conteúdo suficiente/);
  assert.match(source, /Não foi possível carregar os dados agora/);
});

test('formatters centralize the pt-BR number and Babi detection language', () => {
  assert.match(formatters, /Intl\.NumberFormat\('pt-BR'/);
  assert.match(formatters, /Detectado pela Babi/);
});

test('mobile navigation contains the four product sections and defers System', () => {
  assert.match(source, /navigation\.slice\(0, 4\)/);
  assert.match(source, /Mais/);
  assert.match(source, /Sistema/);
});

test('Discovery V2 keeps manual search, presets, progress and blocked copy human', () => {
  assert.match(source, /Buscar produto ou tendência/);
  assert.match(source, /Missões prontas/);
  assert.match(source, /DESCOBERTA EM ANDAMENTO/);
  assert.match(source, /Buscas que estão funcionando/);
  assert.match(source, /A Babi precisa de atenção no TikTok antes de continuar/);
  assert.match(source, /Ver conexão/);
});

test('Opportunities V2 uses human groupings and a progressive detail drawer', () => {
  assert.match(source, /Merecem atenção/);
  assert.match(source, /Em observação/);
  assert.match(source, /SINAIS SATURADOS/);
  assert.match(source, /Análise avançada/);
  assert.match(source, /Por que está aqui/);
  assert.match(source, /Limitações/);
});
test('Library V2 exposes a filtered evidence list and progressive detail in Portuguese', () => {
  assert.match(source, /Buscar na biblioteca/);
  assert.match(source, /Qualidade: Todas/);
  assert.match(source, /Produto identificado/);
  assert.match(source, /Busca: Todas/);
  assert.match(source, /Dados m/);
  assert.match(source, /Carregar mais/);
  assert.match(source, /Hist/);
  assert.match(source, /Detalhes t/);
  assert.match(source, /Sem m/);
  assert.match(source, /Sua biblioteca/);
  assert.match(source, /N/);
});
test('System V2 keeps diagnostics progressive and uses Portuguese human status copy', () => {
  assert.match(source, /data\.overall\.label/);
  assert.match(source, /Navegador/);
  assert.match(source, /Segurança/);
  assert.match(source, /LEITURA DIRETA DE VÍDEOS/);
  assert.match(source, /A pesquisa continua disponível normalmente/);
  assert.match(source, /Diagnóstico avançado/);
  assert.match(source, /QUALIDADE DA BIBLIOTECA/);
  assert.match(source, /Laboratório/);
  assert.match(source, /Fontes externas/);
  assert.match(source, /Nenhuma fonte de marketplace configurada/);
});
