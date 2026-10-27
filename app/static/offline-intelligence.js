/* Text-only persisted insights: no images, external links, browser commands or writes. */
(() => {
 let data=null,filter={};
 const translations={
  'pt-BR':{title:'Inteligência offline',all:'Todos',home:'Casa',kitchen:'Cozinha',cleaning:'Limpeza',organization:'Organização',unclassified:'Unclassified',visual:'Revisão visual necessária',missing:'Candidate ausente',unresolved:'Unresolved',classified:'Classificados',queue:'Fila visual',recall:'Gold Set recall',gaps:'Principais gaps',source:'Somente dados persistidos. Prioridades e grupos são diagnósticos, não novos labels.',shown:'Exibindo',empty:'Nenhum vídeo neste filtro',caption:'Sem caption',reason:'Motivos',generic:'Grupo',priority:'Prioridade visual'},
  'ar-EG':{title:'تحليل البيانات المحفوظة',all:'الكل',home:'البيت',kitchen:'المطبخ',cleaning:'التنظيف',organization:'التنظيم',unclassified:'غير مصنف',visual:'محتاج مراجعة بصرية',missing:'بدون مرشح',unresolved:'عبارات غير محسومة',classified:'مصنف',queue:'قائمة المراجعة البصرية',recall:'استرجاع المجموعة المرجعية',gaps:'فجوات الرصد',source:'بيانات محفوظة فقط. الأولويات تشخيصات وليست تصنيفات بشرية جديدة.',shown:'المعروض',empty:'لا توجد فيديوهات في الفلتر',caption:'بدون نص',reason:'الأسباب',generic:'مجموعة',priority:'أولوية المراجعة البصرية'}
 };
 const t=k=>(translations[document.documentElement.lang]||translations['pt-BR'])[k]||k;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function matches(v){
  if(filter.category && (v.category.primary_category||'unclassified')!==filter.category)return false;
  if(filter.subcategory && v.category.primary_subcategory!==filter.subcategory)return false;
  if(filter.mode==='visual' && !v.visual.eligible)return false;
  if(filter.mode==='missing' && v.has_candidate)return false;
  if(filter.mode==='unresolved' && !v.has_unresolved)return false;
  return true;
 }
 function render(){
  if(!data)return;
  let overview=document.getElementById('offlineOverview');
  if(!overview){overview=document.createElement('section');overview.id='offlineOverview';overview.className='card';document.getElementById('overviewMetrics').append(overview);}
  const s=data.summary;
  overview.innerHTML=`<h2>${esc(t('title'))}</h2><p>${s.videos} videos · ${esc(t('classified'))}: ${s.classified} · ${esc(t('unclassified'))}: ${s.unclassified} · ${esc(t('queue'))}: ${s.visual_queue} · candidates: ${s.candidates} · unresolved: ${s.unresolved}</p><p>${esc(t('recall'))}: ${data.gold_recall===null?'—':(data.gold_recall*100).toFixed(1)+'%'} (${data.gold_progress.reviewed}/${data.gold_progress.total} reviews)</p><p>${esc(t('gaps'))}: ${Object.entries(s.top_detection_gaps).map(([k,n])=>esc(k)+': '+n).join(' · ')}</p>`;
  let root=document.getElementById('offlineInsights');
  if(!root){root=document.createElement('section');root.id='offlineInsights';root.className='card';document.querySelector('[data-section="videos"]').prepend(root);}
  const shown=data.items.filter(matches);
  const buttons=['all','home','kitchen','cleaning','organization','unclassified','visual','missing','unresolved'];
  const active=filter.subcategory||filter.mode||filter.category||'all';
  root.innerHTML=`<h2>${esc(t('title'))}</h2><p>${esc(t('source'))}</p><div class="actions" role="group">${buttons.map(k=>`<button type="button" class="btn secondary" data-offline-filter="${k}" aria-pressed="${active===k}">${esc(t(k))}</button>`).join('')}</div><p role="status">${esc(t('shown'))}: ${shown.length}/${data.items.length}</p><details><summary>${esc(t('queue'))} / ${esc(t('unclassified'))}</summary><div data-offline-results>${shown.map(v=>`<article class="evidence" data-offline-video="${v.video_id}"><b>#${v.video_id} · ${esc(v.category.primary_category||'unclassified')}${v.category.primary_subcategory?' › '+esc(v.category.primary_subcategory):''}</b><p>${esc(v.caption||t('caption'))}</p><p>${esc(t('generic'))}: ${esc(v.primary_group)} · ${esc(t('priority'))}: ${esc(v.visual.priority||'—')}</p><p>${esc(t('reason'))}: ${v.visual.reasons.map(esc).join(', ')}</p></article>`).join('')||esc(t('empty'))}</div></details>`;
  for(const button of root.querySelectorAll('[data-offline-filter]'))button.onclick=()=>{
   const key=button.dataset.offlineFilter;
   filter=['kitchen','cleaning','organization'].includes(key)?{category:'home',subcategory:key}:
    key==='home'||key==='unclassified'?{category:key}:key==='all'?{}:{mode:key};
   render();
  };
 }
 document.getElementById('language')?.addEventListener('change',render);
 fetch('/api/offline-intelligence').then(r=>{if(!r.ok)throw Error('Offline insights unavailable');return r.json();}).then(value=>{data=value;render();}).catch(()=>{});
})();
