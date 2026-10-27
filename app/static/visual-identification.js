/* Assisted visual review. Local API only; never loads remote thumbnails or TikTok. */
(() => {
 const drafts=new Map();let high=[];
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const words={
  'pt-BR':{title:'VISUAL IDENTIFICATION',unavailable:'Imagem indisponível para análise sem TikTok',local:'Vincular imagem já salva em data/visual-images ou data/media',link:'Vincular imagem local',name:'Possível produto',aliases:'Aliases sugeridos (uma por linha)',reason:'Motivo / limites da sugestão',provider:'Provider assistido',version:'Versão ou referência do provider',reference:'URL do resultado (opcional)',confidence:'Confidence declarada (heurística, não probabilidade)',suggest:'Registrar sugestão',accept:'ACEITAR',reject:'REJEITAR',unclear:'INCERTO',boundary:'Aceitar valida somente esta proposta visual; não confirma Product Entity nem altera o Gold Set.',evidence:'Evidence',text:'text',comments:'comments',web:'web listings',search:'Buscar nome semelhante na web (ação manual)',saveWeb:'Guardar evidência web',titleWeb:'Título do resultado',url:'URL',source:'Fonte',match:'Possível correspondência',compatible:'Imagem/listing compatível segundo sua revisão',conflict:'Há contradição',independent:'Revisei a independência desta fonte',group:'Grupo independente (mesmo vendedor/origem = mesmo grupo)',high:'Fila visual HIGH',review:'Revisar',saved:'Salvo. Nenhuma confirmação de produto ou label automático.',error:'Não foi possível salvar a evidência local.',empty:'Sem proposta visual; não inferir nome sem imagem.',notes:'Notas da decisão humana'},
  'ar-EG':{title:'التعرف البصري على المنتج',unavailable:'الصورة غير متاحة للتحليل بدون TikTok',local:'اربط صورة محفوظة في data/visual-images أو data/media',link:'اربط صورة محلية',name:'منتج محتمل',aliases:'أسماء مقترحة، اسم في كل سطر',reason:'سبب وحدود الاقتراح',provider:'مصدر مساعد',version:'إصدار أو مرجع المصدر',reference:'رابط النتيجة اختياري',confidence:'درجة استدلال وليست احتمالا',suggest:'سجل اقتراحا',accept:'قبول',reject:'رفض',unclear:'غير واضح',boundary:'القبول يراجع الاقتراح فقط ولا يؤكد هوية المنتج أو يعدل المجموعة المرجعية.',evidence:'الأدلة',text:'النص',comments:'التعليقات',web:'نتائج الويب',search:'ابحث عن اسم مشابه على الويب يدويا',saveWeb:'احفظ دليل الويب',titleWeb:'عنوان النتيجة',url:'الرابط',source:'المصدر',match:'تطابق محتمل',compatible:'راجعت توافق الصورة والنتيجة',conflict:'فيه تناقض',independent:'راجعت استقلال المصدر',group:'مجموعة المصدر المستقل',high:'قائمة المراجعة ذات الأولوية العالية',review:'راجع',saved:'اتحفظ بدون تأكيد منتج أو تصنيف تلقائي.',error:'تعذر حفظ الدليل المحلي.',empty:'لا يوجد اقتراح بصري؛ لا نستنتج اسما بدون صورة.',notes:'ملاحظات المراجعة البشرية'}
 };
 const t=k=>(words[document.documentElement.lang]||words['pt-BR'])[k]||k;
 async function api(path,body){
  const r=await fetch('/api/visual-identification'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok)throw Error(await r.text());return r.json();
 }
 const input=(label,name,type='text',extra='')=>`<label>${esc(t(label))}<input name="${name}" type="${type}" ${extra}></label>`;
 async function render(videoId,host){
  host=host||document.querySelector('[data-visual-review]');if(!host)return;
  host.dataset.visualVideoId=String(videoId);const marker=String(videoId);
  let item;
  try{item=await api('/videos/'+videoId);}catch{return;}
  if(host.dataset.visualVideoId!==marker||!host.isConnected)return;
  const available=item.image.status==='available';const eligible=item.in_gold_high_pilot!==false;const prepared=item.assisted_prepared!==false;
  host.innerHTML=`<h3>${esc(t('title'))} · #${videoId}</h3><p>${esc(t('boundary'))}</p><p>${esc(item.caption||'—')}</p><p>${esc(item.category||'unclassified')} · ${esc(item.subcategory||'—')} · ${esc(item.product_family||'—')}</p><p>${item.visual_priority_reason.map(esc).join(', ')}</p><h4>VISUAL</h4>${available?`<img src="/api/visual-identification/videos/${videoId}/image" alt="Persisted visual evidence" style="max-width:100%;max-height:320px;object-fit:contain">`:`<p role="status">${esc(t('unavailable'))}: ${esc(item.image.reason)}</p>`}<details><summary>${esc(t('evidence'))} — persisted context</summary><p>Hashtags: ${item.hashtags.map(esc).join(' ')}</p><p>Candidate: ${item.current_candidate.map(x=>esc(x.canonical_name)).join(', ')||'—'}</p><p>Unresolved: ${item.unresolved_phrases.map(x=>esc(x.raw_phrase)).join(', ')||'—'}</p>${item.relevant_comments.map(c=>`<p>#${c.id}: ${esc(c.text)}</p>`).join('')}</details><details><summary>${esc(t('local'))}</summary><form data-visual-local>${input('local','path')}<button type="submit" class="btn secondary">${esc(t('link'))}</button></form></details><form data-visual-proposal><fieldset ${available&&eligible&&prepared?'':'disabled'}><legend>${esc(t('suggest'))}</legend><label>${esc(t('provider'))}<select name="provider"><option>vision_model</option><option>web_image_search</option><option>google_lens_assisted</option></select></label>${input('name','possible_product_name','text','required maxlength="300"')}<label>${esc(t('aliases'))}<textarea name="aliases" maxlength="3600"></textarea></label>${input('reference','result_url','url')}${input('version','provider_version','text','required maxlength="100"')}${input('confidence','confidence','number','min="0" max="1" step="0.01"')}${input('reason','reason','text','required maxlength="4000"')}<button class="btn" type="submit">${esc(t('suggest'))}</button></fieldset></form><div data-visual-proposals>${item.proposals.map(p=>{
   const h=p.hypothesis;
   return `<article class="evidence" data-visual-evidence="${p.id}"><strong>${esc(t('name'))}: ${esc(h.possible_product_name)}</strong><h4>FINAL HYPOTHESIS</h4><p>Canonical suggestion: ${esc(h.canonical_name_suggestion)}</p><p>${esc(t('aliases'))}: ${h.aliases.map(esc).join(', ')||'—'}</p><p>Identity confidence: ${h.identity_confidence} · ${esc(p.review_status)}</p><p>${h.reason.map(esc).join(' · ')}</p><p>${esc(t('evidence'))}: visual ${h.evidence_sources.visual.join(', ')} · ${esc(t('text'))} ${h.evidence_sources.text.map(esc).join(', ')} · ${esc(t('comments'))} ${h.evidence_sources.comments.map(esc).join(', ')} · ${esc(t('web'))} ${h.evidence_sources.web_product_evidence.join(', ')}</p><p>${esc(p.reason)} · ${esc(p.provider)} / ${esc(p.provider_version)} · ${esc(p.observed_at)}</p><label>${esc(t('notes'))}<input data-visual-notes maxlength="4000"></label><div class="actions">${[['accepted','accept'],['rejected','reject'],['unclear','unclear']].map(([status,label])=>`<button type="button" class="btn secondary" data-visual-decision="${status}" data-eid="${p.id}">${esc(t(label))}</button>`).join('')}</div><details><summary>WEB CONFIRMATION</summary><a href="https://www.google.com/search?q=${encodeURIComponent(h.possible_product_name)}" target="_blank" rel="noopener noreferrer">${esc(t('search'))}</a>${p.web_evidence.map(w=>`<p>${esc(w.title)} · ${esc(w.url)} · ${esc(w.match_reason)} · ${esc(w.observed_at)}</p>`).join('')}<form data-visual-web="${p.id}">${input('titleWeb','title','text','required maxlength="1000"')}${input('url','url','url','required')}${input('source','source','text','required')}${input('reason','match_reason','text','required')}<label><input type="checkbox" name="possible_match">${esc(t('match'))}</label><label><input type="checkbox" name="visual_compatible">${esc(t('compatible'))}</label><label><input type="checkbox" name="contradiction">${esc(t('conflict'))}</label><label><input type="checkbox" name="independence_reviewed">${esc(t('independent'))}</label>${input('group','independence_group')}<button class="btn secondary" type="submit">${esc(t('saveWeb'))}</button></form></details></article>`;
  }).join('')||`<p>${esc(t('empty'))}</p>`}</div><p data-visual-message role="status"></p>`;
  addAssetControls(host,item,videoId,available,eligible,prepared);
  const legacyForm=host.querySelector('[data-visual-proposal]');
  const technical=document.createElement('details');
  technical.innerHTML='<summary>Detalhes técnicos — provider / evidência manual</summary>';
  legacyForm.parentNode.insertBefore(technical,legacyForm);technical.append(legacyForm);
  const message=()=>host.querySelector('[data-visual-message]');
  const form=host.querySelector('[data-visual-proposal]');const draftKey=videoId+':'+(item.image.sha256||'unavailable');const draft=drafts.get(draftKey);
  if(draft)for(const [k,val] of Object.entries(draft)){const el=form.querySelector(`[name="${k}"]`);if(el)el.value=val;}
  form.oninput=()=>{const saved={};for(const el of form.querySelectorAll('[name]'))saved[el.name]=el.value;drafts.set(draftKey,saved);};
  form.onsubmit=async ev=>{
   ev.preventDefault();if(!available||!eligible||!prepared)return;
   const value=k=>form.querySelector(`[name="${k}"]`).value;
   const body={provider:value('provider'),possible_product_name:value('possible_product_name'),aliases:value('aliases').split('\n').map(x=>x.trim()).filter(Boolean),result_url:value('result_url')||null,
    provider_version:value('provider_version'),confidence:value('confidence')===''?null:Number(value('confidence')),source_type:'assisted_visual_review',observed_at:new Date().toISOString(),reason:value('reason'),image_sha256:item.image.sha256};
   try{await api('/videos/'+videoId+'/suggestions',body);drafts.delete(draftKey);if(host.dataset.visualVideoId===String(videoId))await render(videoId,host);}catch(e){message().textContent=t('error')+' '+e.message;}
  };
  host.querySelector('[data-visual-local]').onsubmit=async ev=>{
   ev.preventDefault();try{await api('/videos/'+videoId+'/image',{relative_path:ev.currentTarget.querySelector('[name="path"]').value,source_type:'local_frame'});if(host.dataset.visualVideoId===String(videoId))await render(videoId,host);}catch(e){message().textContent=t('error')+' '+e.message;}
  };
  for(const button of host.querySelectorAll('[data-visual-decision]'))button.onclick=async()=>{
   button.disabled=true;try{await api('/evidence/'+button.dataset.eid+'/review',{human_reviewed:true,review_status:button.dataset.visualDecision,notes:button.closest('[data-visual-evidence]').querySelector('[data-visual-notes]').value});if(host.dataset.visualVideoId===String(videoId))await render(videoId,host);}catch(e){button.disabled=false;message().textContent=t('error')+' '+e.message;}
  };
  for(const web of host.querySelectorAll('[data-visual-web]'))web.onsubmit=async ev=>{
   ev.preventDefault();const val=k=>web.querySelector(`[name="${k}"]`).value,checked=k=>web.querySelector(`[name="${k}"]`).checked;
   try{await api('/evidence/'+web.dataset.visualWeb+'/product-search',{title:val('title'),url:val('url'),source:val('source'),observed_at:new Date().toISOString(),possible_match:checked('possible_match'),match_reason:val('match_reason'),visual_compatible:checked('visual_compatible'),contradiction:checked('contradiction'),independence_reviewed:checked('independence_reviewed'),independence_group:val('independence_group')||null});if(host.dataset.visualVideoId===String(videoId))await render(videoId,host);}catch(e){message().textContent=t('error')+' '+e.message;}
  };
 }
 function addAssetControls(host,item,videoId,available,eligible,prepared){
  const ar=document.documentElement.lang==='ar-EG';
  const label=(pt,arabic)=>ar?arabic:pt;
  const controls=document.createElement('section');controls.className='evidence';
  controls.innerHTML=`<div data-asset-drop role="group" aria-label="${label('Adicionar imagem local','إضافة صورة محلية')}" style="border:1px dashed currentColor;padding:12px"><label class="btn secondary">${label('Adicionar imagem — selecionar arquivo','إضافة صورة — اختيار ملف')}<input data-asset-file type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"></label><p>${label('Ou arraste e solte uma imagem aqui. JPG, PNG ou WebP; máximo 10 MiB.','أو اسحب صورة هنا. JPG أو PNG أو WebP، حد أقصى 10 MiB.')}</p></div><p>${available?label('visual_available — imagem local associada','صورة محلية متاحة'):'visual_unavailable'}</p><button type="button" class="btn" data-assisted-start ${available&&eligible?'':'disabled'}>${label('IDENTIFICAR PRODUTO','التعرف على المنتج')}</button>${!eligible?`<p>${label('Piloto inicial: somente HIGH já revisados no Gold Set; FN primeiro.','التجربة الأولى: عناصر HIGH المراجعة فقط، وFN أولا.')}</p>`:''}<p data-asset-message role="status"></p><div data-lens-assisted></div>`;
  host.insertBefore(controls,host.querySelector('[data-visual-proposal]'));
  if(available){const zone=controls.querySelector('[data-asset-drop]'),details=document.createElement('details');details.innerHTML='<summary>Local asset: replace (technical)</summary>';zone.parentNode.insertBefore(details,zone);details.append(zone);const labelNode=zone.querySelector('label');labelNode.firstChild.textContent='Substituir imagem ';}
  const msg=controls.querySelector('[data-asset-message]');let busy=false;
  async function upload(file){
   if(busy||host.dataset.visualVideoId!==String(videoId))return;
   if(!file||!/(?:\.jpe?g|\.png|\.webp)$/i.test(file.name)||file.size<1||file.size>10*1024*1024){msg.textContent=label('Escolha uma imagem JPG/PNG/WebP com até 10 MiB.','اختر صورة JPG/PNG/WebP حتى 10 MiB.');return;}
   busy=true;msg.textContent=label('Validando e associando a imagem…','جار التحقق من الصورة وربطها…');
   try{
    const response=await fetch(`/api/visual-identification/videos/${videoId}/assets?filename=${encodeURIComponent(file.name)}`,{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream'},body:file});
    if(!response.ok)throw Error(await response.text());
    await response.json();if(host.dataset.visualVideoId===String(videoId))await render(videoId,host);
   }catch(error){msg.textContent=label('Imagem não salva: ','الصورة لم تحفظ: ')+error.message;}finally{busy=false;}
  }
  controls.querySelector('[data-asset-file]').onchange=event=>upload(event.target.files?.[0]);
  const zone=controls.querySelector('[data-asset-drop]');
  zone.ondragover=event=>{event.preventDefault();zone.style.outline='2px solid currentColor';};
  zone.ondragleave=()=>{zone.style.outline='';};
  zone.ondrop=event=>{event.preventDefault();zone.style.outline='';const files=event.dataTransfer?.files;if(files?.length===1)return upload(files[0]);msg.textContent=label('Solte somente uma imagem por vídeo.','صورة واحدة لكل فيديو.');};
  controls.querySelector('[data-assisted-start]').onclick=async function(){
   if(!available||!eligible||host.dataset.visualVideoId!==String(videoId))return;
   this.disabled=true;
   try{await api('/videos/'+videoId+'/assisted-identification',{image_sha256:item.image.sha256});if(host.dataset.visualVideoId===String(videoId))await render(videoId,host);}catch(error){this.disabled=false;msg.textContent=error.message;}
  };
  if(available&&eligible&&prepared){
   const lens=controls.querySelector('[data-lens-assisted]');
   lens.innerHTML=`<h4>GOOGLE LENS — ASSISTED</h4><p>${label('Pacote preparado para este vídeo. Baixe a imagem local, abra o Lens e selecione o arquivo manualmente. Nada é enviado ao provider pela Babi.','البيانات جاهزة. نزّل الصورة وافتح Lens واختر الملف يدويا. Babi لا ترسل الصورة لأي مصدر.')}</p><div class="actions"><a class="btn secondary" href="/api/visual-identification/videos/${videoId}/image?download=true" download>${label('Baixar imagem local','تنزيل الصورة المحلية')}</a><a class="btn secondary" href="https://lens.google/" target="_blank" rel="noopener noreferrer">${label('Abrir Lens manualmente','افتح Lens يدويا')}</a></div><form data-lens-result>${input('name','possible_product_name','text','required maxlength="300"')}${input('reference','result_url','url','required')}${input('source','source','text','required maxlength="120"')}${input('titleWeb','listing_title','text','required maxlength="1000"')}<label>observed_at<input name="observed_at" value="${new Date().toISOString()}" required></label><label>notes<textarea name="notes" maxlength="2000" required></textarea></label><button class="btn secondary" type="submit">${label('Registrar resultado como Suggested','تسجيل النتيجة كاقتراح')}</button></form>`;
   lens.querySelector('[data-lens-result]').onsubmit=async event=>{
    event.preventDefault();const form=event.currentTarget;const value=k=>form.querySelector(`[name="${k}"]`).value;
    try{await api('/videos/'+videoId+'/lens-assisted',{image_sha256:item.image.sha256,possible_product_name:value('possible_product_name'),result_url:value('result_url'),source:value('source'),listing_title:value('listing_title'),observed_at:value('observed_at'),notes:value('notes')});if(host.dataset.visualVideoId===String(videoId))await render(videoId,host);}catch(error){msg.textContent=error.message;}
   };
  }
  for(const article of host.querySelectorAll('[data-visual-evidence]')){
   const proposal=item.proposals.find(p=>String(p.id)===article.dataset.visualEvidence);
   if(proposal?.image_matches_current===false){
    const warning=document.createElement('p');warning.textContent=label('Imagem anterior — somente histórico. A proposta não pertence à imagem atual.','صورة سابقة — سجل فقط. الاقتراح لا يخص الصورة الحالية.');article.prepend(warning);
    for(const element of article.querySelectorAll('button,input,textarea,select'))element.disabled=true;
    continue;
   }
   if(!eligible||!proposal)continue;
   const comparison=document.createElement('details');
   comparison.innerHTML=`<summary>${label('Comparação separada com Gold Set — labels preservados','مقارنة منفصلة — التصنيفات الأصلية محفوظة')}</summary><p>${label('Nome humano existente','الاسم البشري الحالي')}: ${esc(item.gold_reference_name||'—')}</p><form data-visual-assessment><label>visual_name_match<select name="match"><option value="unclear">Unclear</option><option value="exact">Exact</option><option value="acceptable">Acceptable</option><option value="wrong">Wrong</option></select></label><label>visual_helpful<select name="helpful"><option value="">Unassessed</option><option value="yes">Yes</option><option value="no">No</option></select></label><label>Notes<input name="notes" maxlength="4000"></label><button class="btn secondary" type="submit">${label('Salvar comparação visual, sem alterar Gold','احفظ المقارنة بدون تعديل التصنيفات')}</button></form>`;
   article.append(comparison);
   comparison.querySelector('form').onsubmit=async event=>{
    event.preventDefault();const form=event.currentTarget;const val=k=>form.querySelector(`[name="${k}"]`).value;
    try{await api('/evidence/'+proposal.id+'/gold-comparison',{human_reviewed:true,name_match:val('match'),helpful:val('helpful')===''?null:val('helpful')==='yes',notes:val('notes')});msg.textContent=label('Comparação salva; Gold Set intacto.','المقارنة محفوظة والتصنيفات الأصلية لم تتغير.');}catch(error){msg.textContent=error.message;}
   };
  }
 }
 window.renderVisualIdentification=render;
 async function queue(){
  let result;try{result=await api('');}catch{return;}
  const pilot=result.gold_high_pilot||[];const order=new Map(pilot.map((v,i)=>[v.video_id,i]));
  high=[...result.high_queue].sort((a,b)=>(order.get(a.video_id)??1000)-(order.get(b.video_id)??1000));
  const parent=document.querySelector('[data-section="videos"]');if(!parent)return;
  let root=document.getElementById('visualHighQueue');if(!root){root=document.createElement('section');root.id='visualHighQueue';root.className='card';parent.prepend(root);}
  root.innerHTML=`<details><summary>${esc(t('high'))} (${high.length}/${result.max_visual_items})</summary><p>Gold pilot: ${pilot.length} · FN first</p><div class="actions">${high.map(v=>`<button class="btn secondary" type="button" data-visual-open="${v.video_id}">${esc(t('review'))} #${v.video_id}${pilot.find(x=>x.video_id===v.video_id)?.benchmark_category==='fn'?' · FN':''}${v.image.status==='available'?' · visual_available':''}</button>`).join('')}</div><div data-visual-queue-review></div></details>`;
  for(const button of root.querySelectorAll('[data-visual-open]'))button.onclick=()=>render(Number(button.dataset.visualOpen),root.querySelector('[data-visual-queue-review]'));
 }
 const current=document.querySelector('[data-visual-review]');if(current)render(Number(current.dataset.visualReview),current);
 document.getElementById('language')?.addEventListener('change',()=>{queue();const host=document.querySelector('[data-visual-review]');if(host)render(Number(host.dataset.visualReview),host);});
 queue();
})();
