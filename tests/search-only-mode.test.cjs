const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {domFixture}=require('./dom-fixture.cjs');
test('paused direct reader guard rejects video/profile and permits search without browser requests',async()=>{
 const source=fs.readFileSync('extension/background.js','utf8');
 const guard=source.slice(source.indexOf('globalThis.ProductHunterDirectMode='),source.indexOf('globalThis.PH_TARGET_SAFETY='));
 const context=vm.createContext({URL,chrome:{storage:{local:{get:async()=>({directVideoEnrichment:{status:'PAUSED'}})}}}});
 vm.runInContext(guard,context);
 for(const path of ['/@maker/video/123','/video/123','/@maker'])await assert.rejects(context.ProductHunterDirectMode.assertAllowed('https://www.tiktok.com'+path),/PAUSED/);
 await assert.rejects(context.ProductHunterDirectMode.assertAllowed(),/PAUSED/);
 await context.ProductHunterDirectMode.assertAllowed('https://www.tiktok.com/search?q=home+gadgets');
});
test('paused dashboard displays search evidence and disables direct pilot without auto requests',async()=>{
 const {document}=domFixture('<section id="directEnrichmentNotice"></section><section id="topCandidates"></section>');const calls=[];
 const data={operational:{direct_video_enrichment:{status:'PAUSED'},search_collection:'BLOCKED',page:'challenge',session:'unconfirmed',global_security:'BLOCKED'},challenge_history:[],counts:{HIGH:1},items:[{video_id:1,platform_video_id:'123',priority:'HIGH',caption:'soap dispenser',why:['search evidence'],features:{},current_intelligence:{purchase_intent:{status:'INSUFFICIENT'}},search_intelligence:{early_signal_confidence:'PARTIAL',recurrence:2,query_diversity:2},enrichment_status:'DIRECT_ENRICHMENT_PAUSED'}]};
 vm.runInContext(fs.readFileSync('app/static/selective-enrichment.js','utf8'),vm.createContext({document,setInterval:()=>{},fetch:async(path,options)=>{calls.push([path,options]);return {ok:true,json:async()=>data}}}));
 for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));
 assert.match(document.getElementById('directEnrichmentNotice').textContent,/DIRECT VIDEO ENRICHMENT PAUSED/);
 const host=document.getElementById('topCandidates');assert.match(host.textContent,/Purchase Intent: INSUFFICIENT/);assert.match(host.textContent,/SEARCH_ONLY/);
 assert.equal(host.querySelectorAll('a').length,0);assert.ok(host.querySelector('[data-selective-start]').hasAttribute('disabled'));
 assert.deepEqual(calls,[['/api/selective-enrichment',undefined]]);
});
