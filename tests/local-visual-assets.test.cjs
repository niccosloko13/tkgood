const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {parseHTML}=require('linkedom');
const code=fs.readFileSync('app/static/visual-identification.js','utf8');
const settle=()=>new Promise(r=>setImmediate(r));
test('file selection/drop upload to the correct video, then explicit identification prepares only local context',async()=>{
 for(const language of ['pt-BR','ar-EG']){
  const {document}=parseHTML(`<html lang="${language}"><body><section data-section="videos"></section><section data-visual-review="4"></section></body></html>`);
  const item={video_id:4,image:{status:'visual_unavailable',reason:'blocked_by_security_stop_tiktok_cdn'},caption:'caption',category:null,subcategory:null,product_family:null,
   hashtags:[],visual_priority_reason:['no_text'],current_candidate:[],unresolved_phrases:[],relevant_comments:[],proposals:[],in_gold_high_pilot:true,assisted_prepared:false};
  const calls=[];let uploadCount=0;
  const context=vm.createContext({document,Map,Date,console,fetch:async(url,options={})=>{
   assert.ok(url.startsWith('/api/visual-identification'));calls.push({url,options});
   if(url.includes('/assets?')){
    assert.equal(options.method,'POST');assert.ok(options.body.name);
    uploadCount++;item.image={status:'available',sha256:(uploadCount===1?'a':'b').repeat(64)};item.assisted_prepared=false;
   }
   if(url.endsWith('/assisted-identification'))item.assisted_prepared=true;
   return {ok:true,json:async()=>url==='/api/visual-identification'?{high_queue:[item],gold_high_pilot:[{video_id:4,benchmark_category:'fn'}],max_visual_items:14}:item};
  }});context.window=context;
  vm.runInContext(code,context);await settle();
  assert.ok(document.querySelector('[data-assisted-start]').disabled);
  const file={name:'frame.png',type:'image/png',size:123};
  await document.querySelector('[data-asset-file]').onchange({target:{files:[file]}});
  assert.equal(calls.filter(c=>c.url.includes('/assets?')).length,1);
  assert.equal(calls.find(c=>c.url.includes('/assets?')).url,'/api/visual-identification/videos/4/assets?filename=frame.png');
  assert.equal(document.querySelector('[data-visual-review] img').getAttribute('src'),'/api/visual-identification/videos/4/image');
  assert.ok(document.querySelector('[data-visual-proposal] fieldset').hasAttribute('disabled'));
  await document.querySelector('[data-assisted-start]').onclick();
  assert.equal(document.querySelector('[data-visual-proposal] fieldset').hasAttribute('disabled'),false);
  assert.ok(document.querySelector('[data-lens-result]'));
  assert.ok(document.querySelector('a[href="https://lens.google/"]'));
  assert.ok(document.querySelector('a[download]').getAttribute('href').startsWith('/api/visual-identification/'));
  const form=document.querySelector('[data-visual-proposal]');form.querySelector('[name="possible_product_name"]').value='Old image draft';form.oninput();
  await document.querySelector('[data-asset-drop]').ondrop({preventDefault(){},dataTransfer:{files:[{name:'second.png',type:'image/png',size:234}]}});
  assert.notEqual(document.querySelector('[data-visual-proposal] [name="possible_product_name"]').value,'Old image draft');
  assert.ok(document.querySelector('[data-visual-proposal] fieldset').hasAttribute('disabled'));
  const count=calls.length;
  await document.querySelector('[data-asset-file]').onchange({target:{files:[{name:'bad.gif',size:30,type:'image/gif'}]}});
  assert.equal(calls.length,count);
  assert.ok(calls.every(c=>!c.url.includes('gold-set')&&!c.url.includes('tiktok')));
 }
});

test('a late upload completion never replaces the review currently selected by the operator',async()=>{
 const {document}=parseHTML('<html><body><section data-section="videos"></section><section data-visual-review="4"></section></body></html>');
 const item={image:{status:'visual_unavailable',reason:'not_cached'},caption:'caption',category:null,subcategory:null,product_family:null,
  hashtags:[],visual_priority_reason:[],current_candidate:[],unresolved_phrases:[],relevant_comments:[],proposals:[]};
 let finish;const calls=[];
 const context=vm.createContext({document,Map,Date,fetch:async(url,options={})=>{
  calls.push(url);if(url.includes('/assets?'))await new Promise(r=>{finish=r;});
  return {ok:true,json:async()=>url==='/api/visual-identification'?{high_queue:[],max_visual_items:14}:item};
 }});context.window=context;
 vm.runInContext(code,context);await settle();
 const uploading=document.querySelector('[data-asset-file]').onchange({target:{files:[{name:'frame.png',size:100,type:'image/png'}]}});
 await settle();await context.renderVisualIdentification(5);
 finish();await uploading;
 assert.equal(document.querySelector('[data-visual-review]').dataset.visualVideoId,'5');
 assert.equal(calls.filter(u=>u.endsWith('/videos/4')).length,1);
});
