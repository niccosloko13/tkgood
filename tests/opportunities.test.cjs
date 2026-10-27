const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {domFixture}=require('./dom-fixture.cjs');

test('opportunity dashboard renders persisted evidence without emitting content commands',async()=>{
 const {document}=domFixture('<section id="opportunitiesDashboard"></section>');const calls=[];
 const data={top_opportunities:[{display_name:'Window cleaner',lifecycle:'EMERGING',momentum:'HIGH',observation_count:4,query_spread:2,creator_spread:2,velocity_summary:'RISING',acceleration_summary:'RISING',saturation:'LOW',evidence_quality:'MEDIUM',why:[{text:'Apareceu em 2 queries distintas.'}],risks:[],insufficient_signals:[]}],watchlist:[{display_name:'Brush',lifecycle:'EARLY_SIGNAL',momentum:'LOW',observation_count:2,query_spread:1,creator_spread:1,velocity_summary:'INSUFFICIENT',acceleration_summary:'INSUFFICIENT',saturation:'INSUFFICIENT',evidence_quality:'LOW',why:[],risks:[],insufficient_signals:[{text:'Poucas observacoes persistidas.'}]}]};
 vm.runInContext(fs.readFileSync('app/static/opportunities.js','utf8'),vm.createContext({document,fetch:async path=>{calls.push(path);return {ok:true,json:async()=>data}}}));
 for(let i=0;i<3;i++)await new Promise(r=>setImmediate(r));
 const host=document.getElementById('opportunitiesDashboard');
 assert.match(host.textContent,/Window cleaner/);assert.match(host.textContent,/Em observa/);assert.match(host.textContent,/Poucas observacoes/);
 assert.deepEqual(calls,['/api/opportunities']);assert.equal(host.querySelectorAll('button,a,input').length,0);
});
