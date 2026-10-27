const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {parseHTML}=require('linkedom');
test('offline insights render counts/recall and filter text without external requests or images',async()=>{
 for(const lang of ['pt-BR','ar-EG']){
  const {document}=parseHTML('<html lang="'+lang+'"><body><select id="language"></select><div id="overviewMetrics"></div><section data-section="videos"></section></body></html>');
  const item=(id,category,sub,priority)=>({video_id:id,caption:'<img src="https://evil.invalid/">',primary_group:'F',has_candidate:false,has_unresolved:id===2,
    category:{primary_category:category,primary_subcategory:sub},visual:{eligible:true,priority,reasons:['candidate_missing']}});
  const fixture={summary:{videos:3,classified:2,unclassified:1,visual_queue:3,candidates:0,unresolved:1,top_detection_gaps:{no_text:1}},
    gold_recall:5/14,gold_progress:{reviewed:15,total:45},items:[item(1,'home','cleaning','HIGH'),item(2,'home','kitchen','MEDIUM'),item(3,null,null,'LOW')]};
  const calls=[];const context=vm.createContext({document,fetch:async url=>{calls.push(url);assert.equal(url,'/api/offline-intelligence');return {ok:true,json:async()=>fixture};}});
  vm.runInContext(fs.readFileSync('app/static/offline-intelligence.js','utf8'),context);
  await new Promise(r=>setImmediate(r));
  assert.ok(document.getElementById('offlineOverview').textContent.includes('35.7%'));
  assert.equal(document.querySelectorAll('[data-offline-video]').length,3);
  document.querySelector('[data-offline-filter="cleaning"]').onclick();
  assert.equal(document.querySelectorAll('[data-offline-video]').length,1);
  assert.ok(document.querySelector('[data-offline-video="1"]'));
  document.querySelector('[data-offline-filter="unclassified"]').onclick();
  assert.ok(document.querySelector('[data-offline-video="3"]'));
  document.querySelector('[data-offline-filter="unresolved"]').onclick();
  assert.ok(document.querySelector('[data-offline-video="2"]'));
  assert.equal(document.querySelectorAll('#offlineInsights img,#offlineInsights a').length,0);
  assert.deepEqual(calls,['/api/offline-intelligence']);
 }
});
