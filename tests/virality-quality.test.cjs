const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {parseHTML}=require('linkedom');
test('intelligence explains evidence independently of identity and filters without writes',async()=>{
 const {document}=parseHTML(fs.readFileSync('app/static/intelligence-core.html','utf8'));
 const dimension={classification:'STRONG',status:'measured',sample_size:20,unique_sources:1,reason_codes:['AUTHOR_DEDUPLICATED_INTENT'],evidence_ids:[17],intent_types:{LINK_REQUEST:{unique_authors:14,comments:14}}};
 function item(id,strong){return {id,video_id:id,status:'UNRESOLVED',product:null,alternatives:[],category:{},reason_code:'UNRESOLVED_GENERIC_TEXT',quality:{signal_quality:{status:'partial'}},evidence:{visual:[],comments:[],web:[]},technical:{observation:{image:{status:'visual_unavailable'}}},intelligence:{product_signal:['purchase_intent'],creative_signal:[],dimensions:{purchase_intent:{...dimension,classification:strong?'STRONG':'WEAK'}},filters:{strong_purchase_intent:strong}}};}
 const data={items:[item(1,true),item(2,false)],review_queue:[],counts:{AUTO:0,REVIEW:0,UNRESOLVED:2}};
 const calls=[];vm.runInContext(fs.readFileSync('app/static/intelligence-core.js','utf8'),vm.createContext({document,console,fetch:async(url,options={})=>{calls.push({url,options});return {ok:true,json:async()=>data};}}));
 await new Promise(r=>setImmediate(r));
 assert.match(document.getElementById('other').textContent,/STRONG/);
 assert.match(document.getElementById('other').textContent,/14 autores/);
 assert.match(document.getElementById('other').textContent,/17/);
 const select=document.getElementById('intelligence-filter');select.querySelector('[value="strong_purchase_intent"]').selected=true;select.dispatchEvent(new document.defaultView.Event('change'));
 await new Promise(r=>setImmediate(r));
 assert.equal(document.getElementById('other').querySelectorAll('article').length,1);
 assert.equal(document.getElementById('reviews').querySelectorAll('article').length,0);
 assert.ok(calls.every(c=>!c.options.method&&c.url==='/api/intelligence-core'));
});
