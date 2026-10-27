const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');

function setup(saved='pt-BR'){
  const html=fs.readFileSync('app/static/index.html','utf8');
  const {document,window}=parseHTML(html);
  const storage=new Map([['babi.language',saved]]);
  const context=vm.createContext({document,URL,console,setInterval(){},setTimeout(){},
    localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
    fetch:()=>new Promise(()=>{}),alert(){}});
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
  return {document,window,context,storage};
}

test('connection separates fresh companion, page failure, session evidence and security latch',()=>{
 for(const language of ['pt-BR','ar-EG']){
  const {document,context}=setup(language);
  context.bridgeFixture={companion_connected:true,heartbeat_fresh:true,extension_connected:true,
   current_url:'https://www.tiktok.com/',current_page_status:'healthy',tiktok_session_status:'unconfirmed',
   security_stop_active:true,failed_url:'https://www.tiktok.com/@old/video/123'};
  vm.runInContext('uiStatus(bridgeFixture)',context);
  for(const [key,value] of [['COMPANION','connected'],['HEARTBEAT','recent'],['TIKTOK SESSION','unconfirmed'],['CURRENT PAGE','healthy'],['SECURITY STOP','active'],['FAILED URL','https://www.tiktok.com/@old/video/123']]){
   assert.ok(document.querySelector(`[data-connection-state="${key}"]`).textContent.includes(value));
  }
 }
});

test('connection identifies incompatible companion and exposes explicit renewal/read-only check',()=>{
 const {document,context}=setup();
 context.bridgeFixture={companion_connected:true,heartbeat_fresh:true,extension_connected:true,companion_compatible:false,compatibility_status:'COMPANION_DESATUALIZADO',security_stop_active:true};
 vm.runInContext('uiStatus(bridgeFixture)',context);
 assert.match(document.querySelector('[data-connection-state="COMPANION"]').textContent,/COMPANION DESATUALIZADO/);
 assert.ok(document.getElementById('renewSession'));
 assert.ok(document.getElementById('verifySession'));
 assert.match(document.querySelector('[data-connection-state="SECURITY STOP"]').textContent,/active/);
});

test('backlog compact controls and per-video stages render in PT and RTL without a new page',()=>{
 for(const language of ['pt-BR','ar-EG']){
  const {document,context}=setup(language);
  const data={counts:{pending:26,running:1,complete:5,failed:1},items:[{url:'https://www.tiktok.com/@maker/video/123',platform_video_id:'123',enrichment_priority:1100,
    stages:{detail:{status:'complete',reason:'reused'},comments:{status:'running',reason:'bounded'},creator:{status:'pending',reason:'profile'},product_detection:{status:'pending',reason:'after data'},corroboration:{status:'pending',reason:'existing rules'}}}],
    batches:[{id:2,status:'running',video_ids:[1,2,3,4,5],current_video:3,current_step:'comments'}]};
  context.backlogFixture=data;vm.runInContext('uiBacklog=backlogFixture;renderBacklog()',context);
  const root=document.getElementById('enrichmentBacklog');
  assert.ok(root.closest('[data-section="collection"]'));
  assert.match(root.textContent,/26/);assert.match(root.textContent,/3 \/ 5/);
  assert.ok(document.getElementById('nextEnrichmentBatch').hasAttribute('disabled'));
  assert.ok(document.getElementById('stopEnrichmentBatch'));
  for(const step of ['detail','comments','creator','product_detection','corroboration'])assert.ok(root.textContent.includes(step));
  assert.equal(document.documentElement.dir,language==='ar-EG'?'rtl':'ltr');
  data.security_stop={reason:'HTTP 403'};
  vm.runInContext('renderBacklog()',context);
  assert.match(document.getElementById('enrichmentBacklog').textContent,/HTTP 403/);
  assert.ok(document.getElementById('nextEnrichmentBatch').hasAttribute('disabled'));
 }
});

test('toolbar preserves PT/RTL without the retired policy controls',()=>{
  for(const language of ['pt-BR','ar-EG']){
    const {document}=setup(language);
    assert.equal(document.getElementById('quietToggle'),null);
    assert.equal(document.documentElement.dir,language==='ar-EG'?'rtl':'ltr');
  }
});

test('dashboard formats numeric values with pt-BR grouping while preserving text values',()=>{
  const {context}=setup();
  assert.equal(vm.runInContext('formatNumber(11000)',context),'11.000');
  assert.equal(vm.runInContext('formatNumber(68500)',context),'68.500');
  assert.equal(vm.runInContext('formatNumber(14900)',context),'14.900');
  assert.equal(vm.runInContext("datum('7673992589036506388')",context),'7673992589036506388');
});

test('SPA moves the original controls without duplicate IDs or additional requests',()=>{
  const {document,window}=setup();
  const search=document.getElementById('searchForm'),capture=document.getElementById('captureButton');
  const ids=Array.from(document.querySelectorAll('[id]'),x=>x.id);
  assert.equal(ids.length,new Set(ids).size);
  for(const section of ['connection','collection','videos','quality','logs','overview']){
    document.querySelector(`[data-nav="${section}"]`).dispatchEvent(new window.Event('click'));
    const visible=Array.from(document.querySelectorAll('[data-section]')).filter(x=>!x.hidden);
    assert.equal(visible.length,1);assert.equal(visible[0].dataset.section,section);
    assert.equal(document.getElementById('searchForm'),search);
    assert.equal(document.getElementById('captureButton'),capture);
  }
  assert.equal(capture.type,'button');
  assert.equal(search.parentElement.id,'searchControls');
});

test('Egyptian Arabic persists and changes visual labels/direction without changing command values',()=>{
  const {document,window,storage}=setup('ar-EG');
  assert.equal(document.documentElement.dir,'rtl');
  assert.equal(document.getElementById('pageTitle').textContent,'نظرة عامة');
  assert.equal(document.querySelector('[onclick="openTikTok()"]').textContent,'افتح TikTok');
  assert.equal(document.querySelector('option[value="BR"]').value,'BR');
  assert.equal(document.querySelector('option[value="smart_discovery"]').value,'smart_discovery');
  document.querySelector('#language option[value="ar-EG"]').removeAttribute('selected');
  document.querySelector('#language option[value="pt-BR"]').setAttribute('selected','');
  document.getElementById('language').dispatchEvent(new window.Event('change'));
  assert.equal(document.documentElement.dir,'ltr');
  assert.equal(storage.get('babi.language'),'pt-BR');
  assert.equal(document.getElementById('pageTitle').textContent,'Visão Geral');
});

test('drawer renders actual evidence/nulls safely and Escape closes it',()=>{
  const {document,window,context}=setup();
  vm.runInContext(`renderVideos({total:1,items:[{video_url:'https://www.tiktok.com/@test/video/123',video_id:'123',caption:'<img onerror=bad>',field_evidence:{likes:{value:0,source:'video_detail',confidence:.98}}}]},{items:[]});openDrawer(0)`,context);
  assert.equal(document.getElementById('videoDrawer').hidden,false);
  assert.match(document.getElementById('drawerContent').textContent,/video_detail/);
  assert.match(document.getElementById('drawerContent').textContent,/98%/);
  assert.equal(document.getElementById('drawerContent').querySelector('img'),null);
  assert.equal(document.getElementById('workspace').inert,true);
  const event=new window.Event('keydown');event.key='Escape';document.dispatchEvent(event);
  assert.equal(document.getElementById('videoDrawer').hidden,true);
  assert.equal(document.getElementById('workspace').inert,false);
});

test('creator is clickable, profile/related URLs stay navigable and read submits only the semantic command',async()=>{
  const {document,window,context}=setup();
  const sent=[];
  context.fetch=async(url,options={})=>{
    if(options.method==='POST'){sent.push(JSON.parse(options.body));return {ok:true,json:async()=>({id:8,status:'PENDING'})};}
    return new Promise(()=>{});
  };
  vm.runInContext(`uiCreators=[{creator_id:1,username:'@maker',profile_url:'https://www.tiktok.com/@maker',observation_count:1,latest_observed_at:'2026-10-21',latest_observation:{display_name:'Maker',bio:'<script>unsafe</script>',followers:31200,following:123,total_likes:1400000,video_count:null,field_evidence:{followers:{value:31200,raw_value:'31.2K',source:'creator_profile',confidence:.98,extractor_version:'tiktok-creator-profile-v1'}}},links:[],signals:{creator_size_bucket:'small'},related_videos:[{video_url:'https://www.tiktok.com/@maker/video/123',video_id:'123',caption:'Library caption',creator_independence_score:null,metric_evidence:{}}]}];renderVideos({total:1,items:[{video_url:'https://www.tiktok.com/@maker/video/123',video_id:'123',creator_username:'@maker'}]});`,context);
  vm.runInContext("uiCreatorCommands=[{id:9,query:'https://www.tiktok.com/@other',status:'FAILED',detail:'other profile'},{id:3,query:'https://www.tiktok.com/@maker',status:'SUCCEEDED',detail:'matching profile'}]",context);
  document.querySelector('[data-creator-for-video]').dispatchEvent(new window.Event('click',{bubbles:true}));
  assert.equal(document.getElementById('videoDrawer').hidden,false);
  assert.match(document.getElementById('drawerTitle').textContent,/Perfil/);
  assert.match(document.getElementById('drawerContent').textContent,/31\.200/);
  assert.match(document.getElementById('drawerContent').textContent,/#3 SUCCEEDED/);
  assert.ok(!document.getElementById('drawerContent').textContent.includes('other profile'));
  assert.equal(document.getElementById('drawerContent').querySelector('script'),null);
  const links=Array.from(document.getElementById('drawerContent').querySelectorAll('a'));
  assert.ok(links.some(a=>a.href==='https://www.tiktok.com/@maker'));
  assert.ok(links.some(a=>a.href==='https://www.tiktok.com/@maker/video/123'));
  document.getElementById('readCreatorButton').dispatchEvent(new window.Event('click',{bubbles:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(sent,[{type:'READ_CREATOR_PROFILE',video_url:'https://www.tiktok.com/@maker/video/123'}]);
});

test('product candidate drawer exposes provenance and safe URLs in PT and Arabic',()=>{
  for(const language of ['pt-BR','ar-EG']){
    const {document,window,context}=setup(language);
    vm.runInContext(`uiCandidates=[{id:1,canonical_name:'Portable Blender',status:'observed',confidence:.42,unique_video_count:1,unique_creator_count:1,supporting_comment_count:0,source_type_count:1,evidence_count:1,first_seen_at:'2026-10-21',last_seen_at:'2026-10-21',detection_version:'product-candidate-v1',confidence_components:{caption:.42},primary_reference_url:'https://www.tiktok.com/@maker/video/1',aliases:[{alias:'Portable Blender'}],urls:[{url:'https://www.tiktok.com/@maker/video/1',url_type:'video',source:'caption'}],evidence:[{evidence_type:'caption',source_entity_type:'videos',source_entity_id:'1',video_id:1,creator_id:1,raw_text:'<script>Portable Blender</script>',extracted_text:'Portable Blender',source_url:'https://www.tiktok.com/@maker/video/1',confidence:.42,observed_at:'2026-10-21',extractor_version:'product-candidate-v1'}]}];renderCandidates();`,context);
    const button=document.querySelector('[data-candidate]');
    button.dispatchEvent(new window.Event('click',{bubbles:true}));
    assert.equal(document.getElementById('videoDrawer').hidden,false);
    const content=document.getElementById('drawerContent');
    assert.match(content.textContent,/product-candidate-v1/);
    assert.match(content.textContent,/42%/);
    assert.match(content.textContent,/2026-10-21/);
    assert.match(content.textContent,/<script>Portable Blender<\/script>/);
    assert.equal(content.querySelectorAll('script').length,0);
    assert.equal(content.querySelector('a').href,'https://www.tiktok.com/@maker/video/1');
    assert.equal(document.documentElement.dir,language==='ar-EG'?'rtl':'ltr');
    assert.equal(vm.runInContext("candidateLink('javascript:alert(1)')",context),'javascript:alert(1)');
    vm.runInContext('closeDrawer()',context);
    assert.equal(document.getElementById('videoDrawer').hidden,true);
  }
});

test('candidate diversity, relationships and gap reasons remain explicit in PT/RTL',()=>{
  for(const language of ['pt-BR','ar-EG']){
    const {document,context}=setup(language);
    const data={items:[],coverage:{videos_processed:17,videos_without_candidate:11,no_candidate_reasons:{unknown_product_phrase:1,no_text:4},detection_gaps:[{video_url:'https://www.tiktok.com/@maker/video/1',reason:'unknown_product_phrase'}]},unresolved_phrases:[{raw_phrase:'Mini Vacuum Cleaner',status:'pending',video_url:'https://www.tiktok.com/@maker/video/1',observations:[{raw_text:'<script>vacuum cleaner</script>',observed_at:'2026-10-21'}]}]};
    vm.runInContext(`setCandidateData(${JSON.stringify(data)});renderCandidates()`,context);
    assert.match(document.getElementById('productCandidates').textContent,/6 \/ 17/);
    assert.match(document.getElementById('productCandidates').textContent,/Mini Vacuum Cleaner/);
    assert.equal(document.getElementById('productCandidates').querySelector('script'),null);
    const c={id:1,status:'observed',evidence_count:26,unique_evidence_groups:1,unique_video_count:1,independent_creator_count:1,unique_commenter_count:0,source_type_count:2,source_diversity_score:25,signature:'window cleaner',corroboration_reason:{independent_videos:1,independent_creators:1,rule_ids:[]},evidence_groups:[{group_key:'video:1',evidence_ids:[1,2,3],identity_support:true}],source_diversity_components:{videos:12},confidence_components:{base_identity:.42,cross_video:0},confidence_cap:.49,confidence_version:'product-corroboration-v1',relationships:[{candidate_a:1,candidate_b:2,name_a:'Dish Brush',name_b:'Floor Brush',relationship_type:'same_video',score:.4,reason:'Shared video',evidence:{video_ids:[1]}}]};
    context.testCandidate=c;
    vm.runInContext("document.getElementById('drawerContent').innerHTML=candidateDiversityMarkup(testCandidate)+candidateConfidenceMarkup(testCandidate)+candidateRelationshipsMarkup(testCandidate)",context);
    const content=document.getElementById('drawerContent');
    assert.equal(content.querySelector('[data-semantic-status]').dataset.semanticStatus,'observed');
    assert.match(content.textContent,/26/);
    assert.match(content.textContent,/video:1/);
    assert.match(content.textContent,/Floor Brush/);
    assert.match(content.textContent,/40%/);
    assert.match(content.textContent,/49%/);
    assert.match(content.textContent,/product-corroboration-v1/);
    assert.equal(content.querySelector('[data-candidate]').dataset.candidate,'2');
    assert.equal(document.documentElement.dir,language==='ar-EG'?'rtl':'ltr');
  }
});

test('semantic recurrence and identity dimensions stay separate in PT and RTL',()=>{
  for(const language of ['pt-BR','ar-EG']){
    const {document,context}=setup(language);
    context.semanticFixture={id:8,status:'corroborated',confidence:.64,legacy_status:'corroborated',legacy_confidence:.64,semantic_status:'concept_recurring',detection_confidence:.42,recurrence_confidence:.6,identity_confidence:0,phrase_specificity:.05,specificity_level:'low',independent_video_count:2,independent_creator_count:2,identity_evidence_status:'insufficient',product_matched:false};
    vm.runInContext("document.getElementById('drawerContent').innerHTML=candidateSemanticsMarkup(semanticFixture)",context);
    const root=document.getElementById('drawerContent');
    assert.equal(root.querySelector('[data-semantic-status]').dataset.semanticStatus,'concept_recurring');
    assert.match(root.querySelector('[data-confidence-dimensions]').textContent,/42%.*60%.*0%/);
    assert.doesNotMatch(root.textContent,/CORROBORATED|64%/);
    assert.ok(root.textContent.includes(vm.runInContext("tr('unconfirmedIdentity')",context)));
    assert.equal(document.documentElement.dir,language==='ar-EG'?'rtl':'ltr');
  }
});

test('discovery progress and clean stop are local semantic actions in PT/RTL',async()=>{
  for(const language of ['pt-BR','ar-EG']){
    const {document,window,context}=setup(language),calls=[];
    context.fetch=async(url,options={})=>{if(options.method==='POST'){calls.push({url,body:options.body});return {ok:true,json:async()=>({ok:true})};}return new Promise(()=>{});};
    vm.runInContext("uiDiscoverySessions=[{id:7,query:'home gadgets',status:'RUNNING',visible_start:8,unique_videos:18,new_videos:10,duplicates:4,scroll_count:2,max_scrolls:5}];renderDiscovery()",context);
    const box=document.getElementById('discoveryDepth');
    assert.match(box.textContent,/2 \/ 5/);assert.match(box.textContent,/18 \/ 30/);
    assert.equal(document.getElementById('expandDiscovery').disabled,true);
    document.getElementById('stopDiscovery').dispatchEvent(new window.Event('click'));
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(calls[0].url,'/api/discovery/sessions/7/stop');
    assert.equal(document.documentElement.dir,language==='ar-EG'?'rtl':'ltr');
  }
});

test('unresolved approval changes only local vocabulary and never starts detection or TikTok commands',async()=>{
  const {document,window,context}=setup(),calls=[];
  context.fetch=async(url,options={})=>{calls.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>({vocabulary_version:'product-vocabulary-v2'})};};
  vm.runInContext("uiCandidateCoverage={videos_processed:17,videos_without_candidate:11};uiUnresolvedPhrases=[{id:2,raw_phrase:'Mini Vacuum Cleaner',status:'pending',video_url:'https://www.tiktok.com/@maker/video/1',observations:[]}];renderCandidates()",context);
  document.querySelector('[data-phrase-review][data-decision="approved"]').dispatchEvent(new window.Event('click',{bubbles:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/product-candidates/unresolved-phrases/2/review');
  assert.deepEqual(calls[0].body,{decision:'approved'});
  assert.match(document.getElementById('productCandidates').textContent,/product-vocabulary-v2/);
});
