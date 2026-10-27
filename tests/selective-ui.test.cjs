const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {domFixture}=require('./dom-fixture.cjs');
test('TOP CANDIDATES shows buckets, reasons, intelligence and statuses without auto-start or unsafe captions',async()=>{
 const {document}=domFixture('<section id="topCandidates"></section>');const calls=[];
 const data={limit:5,counts:{HIGH:1,MEDIUM:2,LOW:0,INSUFFICIENT:1},items:[{video_id:1,platform_video_id:'123',video_url:'https://www.tiktok.com/@maker/video/123',priority:'HIGH',caption:'<img src=x onerror=alert(1)>',why:['specific visible product'],features:{query_diversity:2},enrichment_status:'NOT_SELECTED',current_intelligence:{purchase_intent:{status:'partial'}}}]};
 const context=vm.createContext({document,setInterval:()=>{},fetch:async(path,options)=>{calls.push([path,options]);return {ok:true,json:async()=>data};}});
 vm.runInContext(fs.readFileSync('app/static/selective-enrichment.js','utf8'),context);
 for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));
 const host=document.getElementById('topCandidates');assert.match(host.textContent,/TOP CANDIDATES/);assert.match(host.textContent,/specific visible product/);assert.match(host.textContent,/Purchase Intent: partial/);
 assert.equal(host.querySelectorAll('img').length,0);assert.equal(calls.length,1);assert.equal(calls[0][1],undefined);
});
