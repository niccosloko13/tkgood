const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {parseHTML}=require('linkedom');
const code=fs.readFileSync('app/static/visual-identification.js','utf8');
function fixture(available=false,proposals=[]){return {video_id:4,image:{status:available?'available':'visual_unavailable',reason:'blocked_by_security_stop_tiktok_cdn',sha256:'a'.repeat(64)},
 caption:'<img src="https://www.tiktok.com/">',category:null,subcategory:null,product_family:null,visual_priority_reason:['no_text'],hashtags:[],current_candidate:[],unresolved_phrases:[],relevant_comments:[],proposals};}
async function setup(language='pt-BR',item=fixture()){
 const {document}=parseHTML(`<html lang="${language}"><body><select id="language"></select><section data-section="videos"></section><section data-visual-review="4"></section></body></html>`);
 const calls=[];
 const context=vm.createContext({document,URL,Map,Date,console,fetch:async(url,options={})=>{
  assert.ok(url.startsWith('/api/visual-identification'));calls.push({url,options});
  return {ok:true,json:async()=>url==='/api/visual-identification'?{high_queue:[item],max_visual_items:14}:item};
 }});context.window=context;
 vm.runInContext(code,context);await new Promise(r=>setImmediate(r));
 return {document,calls,context};
}
test('unavailable images never create remote image requests or enabled suggestion inputs',async()=>{
 for(const lang of ['pt-BR','ar-EG']){
  const {document,calls}=await setup(lang);
  assert.equal(document.querySelectorAll('[data-visual-review] img').length,0);
  assert.ok(document.querySelector('[data-visual-proposal] fieldset').hasAttribute('disabled'));
  assert.ok(document.getElementById('visualHighQueue'));
  assert.ok(calls.every(c=>!c.options.method));
 }
});
test('manual accept/reject/unclear posts only explicit proposal decisions and never Gold labels',async()=>{
 const proposal={id:7,possible_product_name:'Blender',provider:'vision_model',provider_version:'test',observed_at:'2026-01-01',review_status:'suggested',reason:'uncertain',web_evidence:[],
  hypothesis:{possible_product_name:'Blender',canonical_name_suggestion:'blender',aliases:['Travel blender'],identity_confidence:.25,
   reason:['single_visual_result_is_not_confirmation'],evidence_sources:{visual:[7],text:[],comments:[],web_product_evidence:[]}}};
 const {document,calls}=await setup('pt-BR',fixture(true,[proposal]));
 assert.equal(document.querySelector('[data-visual-review] img').getAttribute('src'),'/api/visual-identification/videos/4/image');
 for(const state of ['accepted','rejected','unclear']){
  await document.querySelector(`[data-visual-decision="${state}"]`).onclick();
  const call=calls.filter(c=>c.options.method==='POST').at(-1);
  assert.equal(call.url,'/api/visual-identification/evidence/7/review');
  const body=JSON.parse(call.options.body);assert.equal(body.human_reviewed,true);assert.equal(body.review_status,state);
 }
 assert.ok(calls.every(c=>!c.url.includes('gold-set')));
});
