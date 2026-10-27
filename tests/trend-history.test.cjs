const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {parseHTML}=require('linkedom');
test('trend uses real intervals and explains sample coverage without a fabricated graph',async()=>{
 const {document}=parseHTML(fs.readFileSync('app/static/intelligence-core.html','utf8'));
 const insufficient={status:'INSUFFICIENT_HISTORY',latest:null,acceleration:{status:'INSUFFICIENT_HISTORY'}};
 const v={id:1,video_id:1,status:'UNRESOLVED',alternatives:[],category:{},quality:{signal_quality:{status:'partial'}},evidence:{visual:[],comments:[],web:[]},technical:{observation:{image:{status:'visual_unavailable'}}},trend_history:{observations:2,momentum:'GROWING',lifecycle:'EARLY_SIGNAL',time_span_seconds:7200,quality:{strength:'LOW'},velocity:{views:{latest:{value:23,from_value:100,to_value:146,from_at:'2026-01-01T00:00:00Z',to_at:'2026-01-01T02:00:00Z',evidence_ids:[1,2]},acceleration:{status:'INSUFFICIENT_HISTORY'}},likes:insufficient},creator_momentum:{creator_arrival_rate:null,creator_concentration:null},reason_codes:['OBSERVED_LOCAL_HISTORY_ONLY'],series:{views:[{value:100},{value:146}]},conflicting_timestamps:{}}};
 const d={counts:{AUTO:0,REVIEW:0,UNRESOLVED:1},items:[v],review_queue:[],trend_history:{snapshots:2,targets:[{target_type:'VIDEO',velocity_ready:true}]}};
 const calls=[];vm.runInContext(fs.readFileSync('app/static/intelligence-core.js','utf8'),vm.createContext({document,console,fetch:async(url,opts={})=>{calls.push({url,opts});return {ok:true,json:async()=>d};}}));await new Promise(r=>setImmediate(r));
 const text=document.getElementById('other').textContent;
 assert.match(text,/23.000/);assert.match(text,/100 → 146/);assert.match(text,/LOW/);assert.match(text,/INSUFFICIENT_HISTORY/);
 assert.match(text,/não velocidade de demanda/);assert.match(document.getElementById('trend-history').textContent,/2 snapshots/);
 assert.equal(document.querySelectorAll('canvas,svg').length,0);assert.ok(calls.every(c=>!c.opts.method));
});
