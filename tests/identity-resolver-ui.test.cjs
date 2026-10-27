const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {parseHTML}=require('linkedom');

function setup(language){
 const html=fs.readFileSync('app/static/index.html','utf8');
 const {document}=parseHTML(html);
 const context=vm.createContext({document,URL,console,setInterval(){},setTimeout(){},
  localStorage:{getItem:()=>language,setItem(){}},fetch:()=>new Promise(()=>{}),alert(){}});
 vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
 return {document,context};
}

test('identity resolver drawer shows score /100, zero possible matches, breakdown and no merge in PT/RTL',()=>{
 for(const language of ['pt-BR','ar-EG']){
  const {document,context}=setup(language);
  const occurrence={candidate_id:8,candidate_name:'escova',creator:'@creator',phrase:'escova',aliases:['escova'],captions:['<script>escova elétrica</script>'],video_url:'https://www.tiktok.com/@creator/video/123'};
  context.fixture={id:8,semantic_status:'concept_recurring',resolver_pairs:[{id:'pair1',identity_score:10,concept_similarity_score:100,semantic_result:'insufficient',resolver_version:'product-identity-resolver-v1',created_at:'2026-10-22',updated_at:'2026-10-22',evidence:{raw_score:10,caps:[],occurrence_a:occurrence,occurrence_b:{...occurrence,creator:'@other'},features:{modifier_overlap:{value:['elétrica'],weight:20,contribution:10,explanation:'Shared modifier'},number_conflict:{value:{a:[],b:[]},weight:-60,contribution:0,explanation:'No numbers'}}}}]};
  vm.runInContext("document.getElementById('drawerContent').innerHTML=candidateResolverMarkup(fixture)",context);
  const root=document.getElementById('drawerContent');
  assert.match(root.textContent,/10\/100/);
  assert.ok(root.textContent.includes(vm.runInContext("tr('notMerged')",context)));
  assert.ok(root.textContent.includes(vm.runInContext("tr('pair_insufficient')",context)));
  assert.equal(root.querySelector('[data-product-identity] b').textContent,'0');
  assert.equal(root.querySelector('[data-resolver-pair]').dataset.resolverPair,'pair1');
  assert.equal(root.querySelectorAll('tbody tr').length,2);
  assert.equal(root.querySelectorAll('script').length,0);
  assert.match(root.textContent,/<script>escova elétrica<\/script>/);
  assert.equal(root.querySelector('a').href,occurrence.video_url);
  assert.equal(document.documentElement.dir,language==='ar-EG'?'rtl':'ltr');
 }
});

test('possible pair is labelled a hypothesis and remains not merged',()=>{
 const {document,context}=setup('pt-BR');
 context.fixture={id:1,resolver_pairs:[{id:'pair2',identity_score:75,concept_similarity_score:80,semantic_result:'possible_same_product',evidence:{features:{commercial_url_match:{value:['https://shop.example/products/a'],weight:75,contribution:75}},raw_score:75,occurrence_a:{candidate_id:1,phrase:'portable blender'},occurrence_b:{candidate_id:2,candidate_name:'mini portable blender',phrase:'mini portable blender'}}}]};
 vm.runInContext("document.getElementById('drawerContent').innerHTML=candidateResolverMarkup(fixture)",context);
 const root=document.getElementById('drawerContent');
 assert.equal(root.querySelector('[data-product-identity] b').textContent,'1');
 assert.match(root.textContent,/75\/100/);
 assert.ok(root.textContent.includes(vm.runInContext("tr('notMerged')",context)));
 assert.doesNotMatch(root.textContent,/PRODUCT_MATCHED|same_product confirmado/);
});
