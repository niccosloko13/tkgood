const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');

function setup(language='pt-BR'){
 const html=fs.readFileSync('app/static/index.html','utf8'),{document,window}=parseHTML(html),calls=[];
 const context=vm.createContext({document,URL,console,setInterval(){},setTimeout(){},localStorage:{getItem:()=>language,setItem(){}},fetch:()=>new Promise(()=>{}),alert(){}});
 vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
 const pending={video_id:1,creator_username:'@creator',caption:'<script>portable blender</script>',url:'https://www.tiktok.com/@creator/video/1',thumbnail_url:'https://remote.example/image.jpg',review_status:'pending',human_reviewed:false,product_presence:null,specificity:null,candidates:[{id:1,canonical_name:'portable blender',human_review:null}],comments:[{text:'wow',author_username:'@a'}],evidence:[]};
 const data={items:[pending,{...pending,video_id:2,candidates:[]}],progress:{total:2,reviewed:0,pending:2,yes:0,no:0,unclear:0},fn_reasons:['unknown_vocabulary','other'],fp_reasons:['generic_term','other']};
 context.dataFixture=data;
 vm.runInContext('uiGold=dataFixture;uiGoldDetails={1:dataFixture.items[0],2:dataFixture.items[1]};renderGoldSet()',context);
 return {document,window,context,calls,data};
}

test('benchmark filters show counts, FN guidance and explicit metadata in PT and RTL',()=>{
 for(const language of ['pt-BR','ar-EG']){
  const {document,context}=setup(language);
  vm.runInContext(`uiGold.items[0].human_reviewed=true;uiGold.items[0].product_presence='yes';uiGold.items[0].candidates[0].human_review={name_match:'wrong'};uiGoldDetails={};renderGoldSet()`,context);
  const fn=document.querySelector('[data-gold-filter="fn"]');
  assert.match(fn.textContent,/\(1\)/);
  fn.onclick();
  assert.equal(document.getElementById('goldForm').dataset.videoId,'1');
  assert.ok(document.querySelector('.gold-fn-notice'));
  assert.equal(document.querySelector('[name="review_method"]').value,'');
  assert.equal(document.querySelector('[name="fn_reason"]').value,'');
  assert.equal(document.querySelector('[name="human_reviewed"]').checked,undefined);
  document.getElementById('goldClassifyFN').click();
  assert.equal(document.getElementById('goldReviewExtra').open,true);
  document.querySelector('[data-gold-filter="tp"]').onclick();
  assert.equal(document.getElementById('goldForm'),null);
  document.querySelector('[data-gold-filter="pending"]').onclick();
  assert.equal(document.getElementById('goldForm').dataset.videoId,'2');
  assert.equal(document.querySelector('.gold-fn-notice'),null);
 }
});

test('export download is available above review and independent of active filter',()=>{
 for(const language of ['pt-BR','ar-EG']){
  const {document}=setup(language);
  document.querySelector('[data-gold-filter="fn"]').onclick();
  const link=document.getElementById('goldExport');
  assert.equal(link.getAttribute('href'),'/api/gold-set/export');
  assert.equal(link.getAttribute('download'),'babi-gold-set-reviews.zip');
  assert.ok(link.textContent.includes('.zip'));
 }
});

test('human review PT/RTL is blank, safe, offline, with no automatic gold labels',()=>{
 for(const language of ['pt-BR','ar-EG']){
  const {document,context}=setup(language),root=document.getElementById('goldReview');
  assert.equal(root.querySelectorAll('script').length,0);
  assert.match(root.textContent,/<script>portable blender<\/script>/);
  assert.equal(root.querySelector('[name="canonical_product_name"]').value,'');
  assert.equal(root.querySelector('[name="raw_product_name"]').value,'');
  assert.equal(root.querySelectorAll('[type="radio"]:checked').length,0);
  assert.equal(root.querySelector('[data-gold-name]').value,'unreviewed');
  assert.equal(root.querySelectorAll('img[src]').length,0);
  assert.ok(root.querySelector('#goldLoadPreview'));
  assert.equal(root.querySelector('.gold-progress progress').getAttribute('value'),'0');
  assert.equal(document.documentElement.dir,language==='ar-EG'?'rtl':'ltr');
  assert.ok(root.textContent.includes(vm.runInContext("tr('goldHuman')",context)));
 }
});

test('review navigation preserves drafts without saving and pending filter works',()=>{
 const {document,context}=setup();
 document.querySelector('[name="canonical_product_name"]').value='Human draft';
 document.getElementById('goldNext').onclick();
 assert.equal(document.getElementById('goldForm').dataset.videoId,'2');
 document.getElementById('goldPrevious').onclick();
 assert.equal(document.querySelector('[name="canonical_product_name"]').value,'Human draft');
 vm.runInContext("uiGold.items[0].human_reviewed=true;uiGoldPending=true;renderGoldSet()",context);
 assert.equal(document.getElementById('goldForm').dataset.videoId,'2');
});

test('only explicit human selections save locally and never send TikTok commands',async()=>{
 const {document,context,calls,data}=setup();
 context.fetch=async(url,options={})=>{
  calls.push({url,options});
  if(options.method==='POST')return {ok:true,json:async()=>({...data.items[0],human_reviewed:true,product_presence:'yes',specificity:'specific'})};
  return {ok:true,json:async()=>data};
 };
 await document.getElementById('goldForm').onsubmit({preventDefault(){}});
 assert.equal(calls.length,0);
 for(const [name,value] of [['product_presence','yes'],['specificity','specific']]){
  const input=document.querySelector(`[name="${name}"][value="${value}"]`);input.checked=true;input.setAttribute('checked','');
 }
 document.querySelector('[name="human_reviewed"]').checked=true;
 document.querySelector('[name="raw_product_name"]').value='human supplied';
 await document.getElementById('goldForm').onsubmit({preventDefault(){}});
 const posts=calls.filter(c=>c.options.method==='POST');
 assert.equal(posts.length,1);assert.equal(posts[0].url,'/api/gold-set/1/review');
 const payload=JSON.parse(posts[0].options.body);
 assert.equal(payload.human_reviewed,true);assert.equal(payload.review_version,'gold-set-v1');
 assert.equal(payload.raw_product_name,'human supplied');assert.equal(payload.canonical_product_name,'');
 assert.ok(calls.every(c=>c.url.startsWith('/api/gold-set')));
});

test('unreviewed benchmark renders unavailable rates instead of false zero accuracy',()=>{
 const {document,context}=setup();
 context.benchmarkFixture={gold_set_version:'gold-set-v1',detector_version:'product-candidate-v1',vocabulary_version:'product-vocabulary-v1',rules_version:'product-corroboration-v1',tp:0,fp:0,fn:0,tn:0,precision:null,recall:null,f1:null,product_naming_accuracy:null,candidate_coverage_videos:8,library_videos:45,evaluated_videos:0,strict_name_aware:{tp:0}};
 vm.runInContext('uiGoldBenchmark=benchmarkFixture;renderGoldSet()',context);
 const text=document.getElementById('goldReview').textContent;
 assert.ok(text.includes(vm.runInContext("tr('goldBenchmarkAfter')",context)));
 assert.equal(document.querySelector('[data-gold-benchmark]').hasAttribute('open'),false);
 assert.doesNotMatch(text,/Precision 0%/);
 assert.doesNotMatch(text,/Precision 0%/);
});

function key(document,window,value,options={},target=document){const event=new window.Event('keydown',{bubbles:true,cancelable:true});Object.assign(event,{key:value,...options});target.dispatchEvent(event);return event;}

test('Y/N/U are explicit presence-only shortcuts, ignored while typing or outside review',()=>{
 for(const language of ['pt-BR','ar-EG']){
  const {document,window,context}=setup(language);
  key(document,window,'y');assert.equal(document.querySelectorAll('[name="product_presence"]:checked').length,0);
  vm.runInContext("uiSection='quality'",context);
  for(const [letter,value] of [['Y','yes'],['n','no'],['u','unclear']]){
   key(document,window,letter);
   assert.equal(document.querySelector('[name="product_presence"]:checked').value,value);
  }
  assert.equal(document.querySelectorAll('[name="specificity"]:checked').length,0);
  assert.equal(document.querySelector('[name="human_reviewed"]').checked,undefined);
  assert.equal(document.querySelector('[name="canonical_product_name"]').value,'');
  key(document,window,'y',{},document.querySelector('[name="review_notes"]'));
  assert.equal(document.querySelector('[name="product_presence"]:checked').value,'unclear');
  key(document,window,'ArrowRight');
  assert.equal(document.getElementById('goldForm').dataset.videoId,'2');
  assert.equal(document.querySelectorAll('[name="product_presence"]:checked').length,0);
 }
});

test('Ctrl+Enter saves and advances without skipping pending videos or double submission',async()=>{
 const {document,window,context,data,calls}=setup();
 vm.runInContext("uiSection='quality';uiGoldPending=true;renderGoldSet()",context);
 context.fetch=async(url,options={})=>{
  calls.push({url,options});
  if(options.method==='POST'){
   data.items[0]={...data.items[0],human_reviewed:true,product_presence:'yes',specificity:'specific'};
   data.progress={...data.progress,reviewed:1,pending:1,yes:1};
   return {ok:true,json:async()=>({...data.items[0],automatic_benchmark:null})};
  }
  return {ok:true,json:async()=>data};
 };
 key(document,window,'y');
 const specific=document.querySelector('[name="specificity"][value="specific"]');specific.checked=true;specific.setAttribute('checked','');
 document.querySelector('[name="human_reviewed"]').checked=true;
 key(document,window,'Enter',{ctrlKey:true});key(document,window,'Enter',{ctrlKey:true});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(calls.filter(c=>c.options.method==='POST').length,1);
 assert.equal(document.getElementById('goldForm').dataset.videoId,'2');
 assert.equal(document.querySelectorAll('[name="product_presence"]:checked').length,0);
 assert.ok(calls.every(c=>c.url.startsWith('/api/gold-set')));
 assert.ok(document.querySelector('#goldReview a[href*="tiktok.com"]').getAttribute('href').startsWith('https://www.tiktok.com/'));
});

test('partial benchmark is clearly marked and exposes counts and top error reasons',()=>{
 const {document,context}=setup();
 context.partial={evaluation_label:'PARTIAL GOLD SET',gold_set_version:'gold-set-v1',detector_version:'product-candidate-v1',vocabulary_version:'product-vocabulary-v1',rules_version:'product-corroboration-v1',reviewed_videos:15,progress:{yes:8,no:5,unclear:2},library_videos:45,tp:5,fp:2,fn:3,tn:3,precision:5/7,recall:5/8,f1:10/15,product_naming_accuracy:.5,fn_reasons:{unknown_vocabulary:2,caption_missing:1},fp_reasons:{generic_term:2},candidate_coverage_videos:8,evaluated_videos:13};
 vm.runInContext('uiGoldBenchmark=partial;renderGoldSet()',context);
 const text=document.querySelector('[data-gold-benchmark]').textContent;
 assert.match(text,/PARTIAL GOLD SET/);assert.match(text,/15 \/ 45/);
 assert.match(text,/TP 5.*FP 2.*FN 3.*TN 3/);
 assert.match(text,/Vocabulário desconhecido: 2/);assert.match(text,/Termo genérico: 2/);
});

test('real video 1 shows persisted product context and technical JSON stays collapsed',()=>{
 const real=JSON.parse(fs.readFileSync('tests/fixtures/gold-review-video-1.json','utf8'));
 for(const language of ['pt-BR','ar-EG']){
  const {document,context}=setup(language);context.realVideo=real;
  vm.runInContext('uiGold.items[0]=realVideo;uiGoldDetails[1]=realVideo;uiGoldDrafts={};renderGoldSet()',context);
  const root=document.getElementById('goldReview');
  assert.match(root.querySelector('.gold-creator').textContent,/@airlandolists/);
  assert.match(root.querySelector('.gold-caption').textContent,/Easy to remove the stains/);
  assert.match(root.querySelector('.gold-hashtags').textContent,/#gadgets/);
  assert.equal(root.querySelectorAll('[data-gold-draft]').length,2);
  const comments=root.querySelector('.gold-comment-list').textContent;
  for(const text of ['vacuum cleaner','Mini Vacuum Cleaner Price? very useful','qual nome do produto?','onde compro um desses?'])assert.ok(comments.includes(text));
  assert.ok(root.querySelectorAll('.gold-comment-list blockquote').length<=8);
  assert.equal(root.querySelector('[data-gold-technical]').hasAttribute('open'),false);
  for(const pre of root.querySelectorAll('pre'))assert.ok(pre.closest('[data-gold-technical]'));
  assert.equal(root.querySelector('[data-gold-benchmark]').hasAttribute('open'),false);
  assert.equal(root.querySelectorAll('img[src]').length,0);
  assert.equal(root.querySelector('[name="raw_product_name"]').value,'');
  const summary=root.querySelector('.gold-evidence-summary');
  assert.equal(summary.children[2].querySelector('b').textContent,'2');
  assert.equal(summary.children[3].querySelector('b').textContent,'30');
  assert.equal(summary.children[4].querySelector('b').textContent,'3');
  assert.equal(summary.children[5].querySelector('b').textContent,'11');
 }
});

test('persisted thumbnail loads only after explicit click and draft chip never labels or saves',()=>{
 const {document,context,calls}=setup();
 context.fetch=async(...args)=>{calls.push(args);return {ok:true,json:async()=>({})};};
 const image=document.querySelector('[data-gold-remote-image]');
 assert.equal(image.hasAttribute('src'),false);
 document.getElementById('goldLoadPreview').onclick();
 assert.equal(image.getAttribute('src'),'https://remote.example/image.jpg');
 image.onload();assert.equal(image.hidden,false);
 assert.equal(document.querySelector('[data-gold-placeholder]').hidden,true);
 vm.runInContext("uiGoldDetails[1].unresolved_phrases=[{raw_phrase:'vacuum cleaner'}];renderGoldSet()",context);
 document.querySelector('[data-gold-draft]').onclick();
 assert.equal(document.querySelector('[name="raw_product_name"]').value,'vacuum cleaner');
 assert.equal(document.querySelector('[name="canonical_product_name"]').value,'');
 assert.equal(document.querySelectorAll('[name="product_presence"]:checked').length,0);
 assert.equal(document.querySelectorAll('[name="specificity"]:checked').length,0);
 assert.ok(!document.querySelector('[name="human_reviewed"]').checked);
 assert.equal(calls.length,0);
});

test('No hides name fields and decisions have strong selected state without changing stored drafts',()=>{
 const {document,window,context}=setup();vm.runInContext("uiSection='quality'",context);
 key(document,window,'y');
 assert.equal(document.querySelector('.gold-name-fields').hidden,false);
 assert.ok(document.querySelector('[value="yes"]').closest('.gold-choice').classList.contains('is-selected'));
 document.querySelector('[name="raw_product_name"]').value='Human draft';
 key(document,window,'n');
 assert.equal(document.querySelector('.gold-name-fields').hidden,true);
 assert.equal(document.querySelector('[name="raw_product_name"]').disabled,true);
 assert.ok(document.querySelector('[value="no"]').closest('.gold-choice').classList.contains('is-selected'));
 key(document,window,'u');
 assert.equal(document.querySelector('.gold-name-fields').hidden,false);
 assert.equal(document.querySelector('[name="raw_product_name"]').value,'Human draft');
});

test('local media has priority and preview playback never autostarts',()=>{
 const {context}=setup();
 context.mediaFixture={video_id:1,local_thumbnail_url:'data:image/png;base64,aW1n',thumbnail_url:'https://remote.example/image.jpg'};
 const local=vm.runInContext('goldThumbnailMarkup(mediaFixture)',context);
 assert.match(local,/data-gold-local-image/);assert.doesNotMatch(local,/goldLoadPreview|remote.example/);
 context.mediaFixture={video_id:1,local_preview_url:'/media/persisted.webm'};
 const preview=vm.runInContext('goldThumbnailMarkup(mediaFixture)',context);
 assert.match(preview,/<video[^>]*preload="none"/);assert.doesNotMatch(preview,/autoplay/);
 assert.equal(vm.runInContext("goldSafeMedia('javascript:alert(1)')",context),null);
});
