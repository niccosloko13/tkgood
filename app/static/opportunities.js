/* Read-only opportunity cockpit. It never emits browser or collection commands. */
(() => {
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const text = item => esc(item?.text || item || '');
  const number = value => typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('pt-BR',{maximumFractionDigits:2}).format(value) : esc(value ?? '—');
  const lifecycle = item => String(item.lifecycle || 'OBSERVED').toUpperCase();
  const momentum = item => String(item.momentum || 'UNKNOWN').toUpperCase();
  const card = (item,index,kind) => {
    const state = lifecycle(item), pace = momentum(item), why = (item.why || []).slice(0,2), risks = (item.risks || []).slice(0,2);
    return `<article class="opportunity-card" data-lifecycle="${esc(state)}" data-kind="${esc(kind)}">
      <header><div><span class="opportunity-rank">${String(index + 1).padStart(2,'0')}</span><h3>${esc(item.display_name || 'Sinal sem nome')}</h3></div><div class="opportunity-state">${esc(state)} · ${esc(pace)}</div></header>
      <div class="opportunity-metrics"><span>Observações<b>${number(item.observation_count)}</b></span><span>Buscas<b>${number(item.query_spread)}</b></span><span>Creators<b>${number(item.creator_spread)}</b></span></div>
      <div class="opportunity-signals"><span>Ritmo: ${esc(item.velocity_summary || 'indisponível')}</span><span>Aceleração: ${esc(item.acceleration_summary || 'indisponível')}</span><span>Saturação: ${esc(item.saturation || 'indisponível')}</span></div>
      <div class="opportunity-evidence"><strong>POR QUE ESTÁ AQUI</strong><ul>${why.map(x => `<li>${text(x)}</li>`).join('') || '<li>Ainda faltam sinais suficientes para explicar este item.</li>'}</ul>
      ${risks.length ? `<div class="opportunity-risk"><strong>Limite</strong> · ${risks.map(text).join(' ')}</div>` : ''}
      ${(item.insufficient_signals || []).length ? `<p class="opportunity-limit">Ainda não medido: ${(item.insufficient_signals || []).slice(0,2).map(text).join(' · ')}</p>` : ''}</div>
    </article>`;
  };
  async function load() {
    const host = document.getElementById('opportunitiesDashboard');
    if (!host) return;
    try {
      const response = await fetch('/api/opportunities');
      if (!response.ok) throw new Error('API');
      const data = await response.json(), top = data.top_opportunities || [], watch = data.watchlist || [];
      host.innerHTML = `<h2>O que merece atenção agora</h2><p class="opportunity-intro">Uma leitura simples dos sinais persistidos: recorrência, diversidade de buscas e movimento observado.</p>
        ${top.length ? `<div class="opportunity-grid">${top.map((item,index) => card(item,index,'top')).join('')}</div>` : '<div class="opportunity-empty">Ainda não há uma oportunidade com evidência suficiente. Acompanhe os sinais em observação abaixo.</div>'}
        <section class="opportunity-watch"><h2>Em observação</h2><p class="opportunity-intro">Sinais iniciais que ainda precisam de mais recorrência ou diversidade.</p>${watch.length ? `<div class="opportunity-grid">${watch.map((item,index) => card(item,index,'watch')).join('')}</div>` : '<p class="opportunity-empty">Nenhum candidato em observação no momento.</p>'}</section>
        <p class="opportunity-basis">Baseado apenas em evidências locais persistidas. Métricas ausentes continuam ausentes — nada é inferido como fato.</p>`;
    } catch (_) {
      host.innerHTML = '<h2>O que merece atenção agora</h2><p class="opportunity-empty">A leitura local de oportunidades não está disponível neste momento.</p>';
    }
  }
  load();
})();
