const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {parseHTML}=require('linkedom');
test('category filters stay in existing library, display counts and preserve RTL',async()=>{
 for(const lang of ['pt-BR','ar-EG']){
  const html=fs.readFileSync('app/static/index.html','utf8'),{document}=parseHTML(html);
  const fixture={taxonomy:{categories:{home:{'pt-BR':'Casa','ar-EG':'البيت',subcategories:{cleaning:{'pt-BR':'Limpeza','ar-EG':'التنظيف'}}}}},items:[{video_id:1,platform_video_id:'123',category:{primary_category:'home',primary_subcategory:'cleaning',category_status:'classified',category_evidence:[]},candidates:[],unresolved:[],queries:['cleaning gadgets'],creator:'@maker',enrichment_status:'pending'}],video_observations:[{video_id:'123',video_url:'https://www.tiktok.com/@maker/video/123',creator_username:'@maker',caption:'floor brush',field_evidence:{}}],total:1,queries:[],plan:{selected_query:'cleaning gadgets'},distribution:{home:1},summary:{unique_creators:1,candidates:0,unresolved:0,unclassified:0},night_runs:[]};
  const calls=[];const context=vm.createContext({document,console,URL,setInterval(){},setTimeout(){},localStorage:{getItem:()=>lang,setItem(){}},fetch:()=>new Promise(()=>{}),alert(){}});context.window=context;
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
  context.fetch=async url=>{calls.push(url);return {ok:true,json:async()=>fixture};};
  vm.runInContext(fs.readFileSync('app/static/category-intelligence.js','utf8'),context);
  await new Promise(r=>setImmediate(r));
  assert.ok(document.getElementById('categoryIntelligence'));
  assert.equal(document.querySelectorAll('#recentVideos .video').length,1);
  assert.equal(document.documentElement.dir,lang==='ar-EG'?'rtl':'ltr');
  const select=document.querySelector('[data-ci-filter="category"]');assert.match(select.textContent,/\(1\)/);
  select.querySelector('option[value="home"]').selected=true;select.onchange();
  assert.equal(document.querySelectorAll('#recentVideos .video').length,1);
  assert.ok(calls.every(url=>url.startsWith('/api/category-intelligence')));
 }
});
