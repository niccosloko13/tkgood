const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {parseHTML}=require('linkedom');
const code=fs.readFileSync('app/static/intelligence-core.js','utf8');
const settle=()=>new Promise(r=>setImmediate(r));
function item(id,status){return {id,video_id:id,product:'Mini <Mop>',status,reason_code:'TEST_REASON',alternatives:['Window Sponge'],category:{},quality:{signal_quality:{status:'insufficient_data'}},evidence:{visual:[],comments:[],web:[]},technical:{observation:{image:{status:'visual_unavailable'}}}};}
async function setup(){
 const {document}=parseHTML(fs.readFileSync('app/static/intelligence-core.html','utf8'));
 const data={items:[item(1,'REVIEW'),item(2,'AUTO'),item(3,'UNRESOLVED')],review_queue:[item(1,'REVIEW')],counts:{AUTO:1,REVIEW:1,UNRESOLVED:1}};
 const calls=[];const context=vm.createContext({document,console,prompt:()=>null,fetch:async(url,options={})=>{calls.push({url,options});assert.ok(url.startsWith('/api/intelligence-core'));return {ok:true,json:async()=>data};}});
 vm.runInContext(code,context);await settle();return {document,calls};
}
test('core review queue contains only REVIEW; absent quality has no zero score',async()=>{
 const {document,calls}=await setup();
 assert.equal(document.querySelectorAll('#reviews article').length,1);
 assert.equal(document.querySelectorAll('#other article').length,2);
 assert.equal(document.querySelectorAll('#reviews img').length,0);
 assert.equal(document.querySelectorAll('#reviews input').length,0);
 assert.ok(document.getElementById('reviews').textContent.includes('Mini <Mop>'));
 assert.ok(document.getElementById('reviews').textContent.includes('insufficient_data'));
 assert.ok(calls.every(c=>!c.options.method));
});
test('confirmation sends only explicit human decision, never a Gold mutation',async()=>{
 const {document,calls}=await setup();
 const button=document.querySelector('[data-confirm="1"]');
 document.getElementById('reviews').onclick({target:button});await settle();
 const post=calls.find(c=>c.options.method==='POST');
 assert.equal(post.url,'/api/intelligence-core/review/1');
 assert.deepEqual(JSON.parse(post.options.body),{human_confirmed:true,action:'confirm',name:'Mini <Mop>'});
 assert.ok(calls.every(c=>!c.url.includes('gold')));
});
test('unresolved identity still displays measured purchase intent and operational readiness',async()=>{
 const {document}=parseHTML(fs.readFileSync('app/static/intelligence-core.html','utf8'));
 const v=item(3,'UNRESOLVED');v.quality.purchase_intent={strength:'STRONG',unique_purchase_intent_comments:3,sample_size:5};
 v.quality.consumer_reaction={status:'measured'};v.quality.product_quality={status:'insufficient_data'};v.quality.commercial_readiness={status:'partial'};
 const data={items:[v],review_queue:[],counts:{AUTO:0,REVIEW:0,UNRESOLVED:1},openclip:{status:'ready'},faiss_index:{vectors:8,generation:'abcdef123'},resource_state:{state:'RUN'},purchase_intent_measured_items:1};
 vm.runInContext(code,vm.createContext({document,console,fetch:async()=>({ok:true,json:async()=>data})}));await settle();
 assert.ok(document.getElementById('other').textContent.includes('STRONG'));
 assert.ok(document.getElementById('operations').textContent.includes('8 vetores'));
 assert.ok(document.getElementById('operations').textContent.includes('ready'));
 assert.equal(document.querySelectorAll('#reviews button').length,0);
});
test('visual identity starts automatically without product name or provider input and hides upload with usable asset',async()=>{
 const {document}=parseHTML(fs.readFileSync('app/static/intelligence-core.html','utf8'));
 const v=item(1,'REVIEW');v.technical.observation.image.status='available';
 const data={items:[v],review_queue:[v],counts:{AUTO:0,REVIEW:1,UNRESOLVED:0},visual_identity:{available_assets:1,needs_visual:1,visual_processed:0,lens_assisted_required:1,visual_hypotheses:0,confirmed:0,conflicted:0}};
 const calls=[];const context=vm.createContext({document,console,setTimeout:()=>0,fetch:async(url,options={})=>{calls.push({url,options});return {ok:true,json:async()=>data};}});
 vm.runInContext(code,context);await settle();
 assert.equal(document.querySelectorAll('[data-add-image]').length,0);
 assert.equal(document.querySelectorAll('input[name="possible_product_name"]').length,0);
 await document.getElementById('visual-run').onclick();await settle();
 const post=calls.find(c=>c.options.method==='POST');assert.equal(post.url,'/api/intelligence-core/visual-start');assert.deepEqual(JSON.parse(post.options.body),{});
 assert.ok([...document.querySelectorAll('img')].every(i=>i.getAttribute('src').startsWith('/api/visual-identification/')));
});
