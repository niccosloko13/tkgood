(() => {
 'use strict';
 const host=document.getElementById('topCandidates');if(!host)return;
 const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const labels={purchase_intent:'Purchase Intent',signal_quality:'Signal Quality',product_quality:'Product Quality',creative_dna:'Creative readiness',trend_readiness:'Trend readiness',commercial_readiness:'Commercial readiness',creator_signal:'Creator Signal',identity:'Identity'};
 const status=x=>x?.classification||x?.status||'insufficient_data';
 function render(data){
  const run=data.last_run,states=new Map((run?.items||[]).map(x=>[x.video_id,x]));
  const mode=data.operational,paused=mode?.direct_video_enrichment?.status==='PAUSED',notice=document.getElementById('directEnrichmentNotice');
  if(notice&&mode){notice.innerHTML=paused?`<h2>DIRECT VIDEO ENRICHMENT PAUSED</h2><p>Repeated challenge during individual video navigation.</p><p>Search collection: <b>${esc(mode.search_collection)}</b> · Page: ${esc(mode.page)} · Session: ${esc(mode.session)} · Global security: ${esc(mode.global_security)}</p><p>Modo SEARCH_ONLY. Search fica AVAILABLE quando página e sessão estão saudáveis e o stop global está liberado por ação autorizada. Nenhuma coleta inicia automaticamente.</p><details><summary>Challenge history (${esc(data.challenge_history?.length||0)})</summary>${(data.challenge_history||[]).map(e=>`<p>${esc(e.timestamp)} · ${esc(e.navigation_mode)} · ${esc(e.stage)}<br>${esc(e.target)}<br>Post-health: ${esc(e.post_health.page)} / ${esc(e.post_health.session)}. Associação de contexto; sem atribuir causalidade ao target.</p>`).join('')}</details>`:'';}
  host.innerHTML=`<h2>TOP CANDIDATES</h2><p>Prioridade para decidir onde coletar dados. Não é ranking final de oportunidade.</p><p>${Object.entries(data.counts).map(([k,v])=>`${esc(k)}: ${esc(v)}`).join(' · ')}</p><p>${run?`Piloto ${esc(run.run.id)}: ${esc(run.run.status)} · ${esc(run.stop_reason||'em andamento')}`:`Máximo ${esc(data.limit)} vídeos HIGH por piloto.`}</p><button type="button" data-selective-refresh>Atualizar candidatos</button> <button type="button" data-selective-start ${paused||run||!data.counts.HIGH?'disabled':''}>${paused?'DIRECT_ENRICHMENT_PAUSED':`Executar piloto HIGH (máx. ${esc(data.limit)})`}</button>${run?.run.status==='RUNNING'?` <button type="button" data-selective-stop="${esc(run.run.id)}">Parar piloto</button>`:''}<div role="status" data-selective-message></div><div class="selective-list">${data.items.slice(0,12).map(v=>{
   const item=states.get(v.video_id),intel=paused?v.current_intelligence:item?.after||item?.before||v.current_intelligence;
   return `<article class="card"><h3>${paused?esc(v.platform_video_id):`<a href="${esc(v.video_url)}" target="_blank" rel="noopener noreferrer">${esc(v.platform_video_id)}</a>`} · ${esc(paused?v.priority:item?.priority.priority||v.priority)}</h3><p>${esc(v.caption||'Caption insuficiente')}</p><p>${esc(paused?v.enrichment_status:item?.status||v.enrichment_status)}</p>${paused?`<p>SEARCH_ONLY · DIRECT_ENRICHMENT_PAUSED<br>Search evidence: ${esc(v.search_intelligence?.early_signal_confidence)} · Recurrence: ${esc(v.search_intelligence?.recurrence)} · Queries: ${esc(v.search_intelligence?.query_diversity)}<br>Comments: unavailable (search-only) · Creator detail: unavailable (search-only)</p>`:''}<details><summary>Why</summary><ul>${(paused?v.why:item?.priority.why||v.why).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><pre>${esc(JSON.stringify(paused?v.features:item?.priority.features||v.features,null,2))}</pre></details><p>${Object.entries(labels).map(([k,label])=>`${esc(label)}: ${esc(status(intel?.[k]))}`).join(' · ')}</p>${item?`<details><summary>Histórico de enrichment: antes / depois e coleta</summary>${Object.entries(labels).map(([k,label])=>`<p>${esc(label)}: ${esc(status(item.before?.[k]))} → ${esc(item.after?status(item.after[k]):'não coletado')}</p>`).join('')}<pre>${esc(JSON.stringify(item.steps,null,2))}</pre></details>`:''}</article>`;
  }).join('')}</div>`;
 }
 async function load(){try{const r=await fetch('/api/selective-enrichment');if(!r.ok)throw Error(await r.text());render(await r.json());}catch(e){host.textContent='TOP CANDIDATES: '+e.message;}}
 host.addEventListener('click',async event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.hasAttribute('data-selective-refresh'))return load();
  const path=b.hasAttribute('data-selective-start')?'/api/selective-enrichment/start':b.dataset.selectiveStop?`/api/selective-enrichment/${b.dataset.selectiveStop}/stop`:null;
  if(!path)return;
  b.disabled=true;
  try{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!r.ok)throw Error(await r.text());await load();}catch(e){host.querySelector('[data-selective-message]').textContent=e.message;b.disabled=false;}
 });
 load();setInterval(load,10000);
})();
