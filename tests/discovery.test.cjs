const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');

function fixture(){
  let scrolls=0,visible=[1,2],allowed=true;
  const doc={location:{href:'https://www.tiktok.com/search?q=home+gadgets'},visibilityState:'visible',body:{innerText:''},
    scrollingElement:{scrollHeight:4000,clientHeight:1000,scrollTop:0,scrollBy(){scrolls++;this.scrollTop+=800;visible=[2,3];}},querySelectorAll(){return [];}};
  const context=vm.createContext({URL,console,setTimeout,ProductHunterSearch:{visible:()=>true,videoUrl:href=>href,extractSearchResults:()=>visible.map((id,index)=>({video_id:String(id),video_url:`https://www.tiktok.com/@a/video/${id}`,search_position:index+1,card_snapshot:'large snapshot'}))}});
  vm.runInContext(fs.readFileSync('extension/search_discovery.js','utf8'),context);
  const api=context.ProductHunterDiscovery;
  const env={doc,win:{innerHeight:1000},sleep:async()=>{},permit:async()=>({allowed,waiting:!allowed})};
  return {doc,api,env,getScrolls:()=>scrolls,setAllowed:value=>{allowed=value;}};
}

test('discovery reads viewport zero, scrolls search only and retries cached viewport without movement',async()=>{
  const f=fixture(),options={command_id:1,query:'home gadgets',scroll_iteration:0};
  const first=await f.api.viewportStep(options,f.env);
  assert.equal(f.getScrolls(),0);
  assert.deepEqual(Array.from(first.capture.results,v=>v.video_id),['1','2']);
  options.scroll_iteration=1;options.document_token=first.document_token;
  const second=await f.api.viewportStep(options,f.env);
  assert.deepEqual(Array.from(second.capture.results,v=>v.video_id),['2','3']);
  assert.equal(f.getScrolls(),1);
  await f.api.viewportStep(options,f.env);assert.equal(f.getScrolls(),1);
  assert.equal(second.capture.results[0].card_snapshot,null);
});

test('feed, changed query, challenge and cancellation cannot scroll',async()=>{
  for(const mode of ['feed','query','challenge','cancelled']){
    const f=fixture();
    if(mode==='feed')f.doc.location.href='https://www.tiktok.com/foryou';
    if(mode==='query')f.doc.location.href='https://www.tiktok.com/search?q=other';
    if(mode==='hidden')f.doc.visibilityState='hidden';
    if(mode==='challenge')f.doc.body.innerText='Verify you are human';
    if(mode==='cancelled')f.setAllowed(false);
    await assert.rejects(f.api.viewportStep({command_id:1,query:'home gadgets',scroll_iteration:0},f.env));
    assert.equal(f.getScrolls(),0);
  }
});

test('out-of-order, over-limit and changed document steps are refused',async()=>{
  const f=fixture();
  await assert.rejects(f.api.viewportStep({command_id:1,query:'home gadgets',scroll_iteration:6},f.env));
  await assert.rejects(f.api.viewportStep({command_id:2,query:'home gadgets',scroll_iteration:1},f.env));
  await f.api.viewportStep({command_id:1,query:'home gadgets',scroll_iteration:0},f.env);
  await assert.rejects(f.api.viewportStep({command_id:1,query:'home gadgets',scroll_iteration:1,document_token:'different'},f.env));
  assert.equal(f.getScrolls(),0);
});

test('Python and Companion conservative discovery limits agree',()=>{
  const {api}=fixture();const config=JSON.parse(fs.readFileSync('config/discovery.json','utf8'));
  assert.equal(api.LIMITS.maxScrolls,config.max_scrolls);
  assert.equal(api.LIMITS.maxUnique,config.max_unique_videos);
  assert.equal(api.LIMITS.maxRuntime,config.max_runtime_seconds*1000);
});

test('nested search-result scroller is selected instead of a nonmoving document root',()=>{
  const f=fixture();
  const links=[1,2].map(id=>({getAttribute:()=>`https://www.tiktok.com/@a/video/${id}`}));
  const scroller={scrollHeight:4000,clientHeight:1000,parentElement:f.doc.body,closest:()=>null,querySelectorAll:()=>links};
  links.forEach(link=>{link.parentElement=scroller;});
  f.doc.querySelectorAll=()=>links;f.env.win.getComputedStyle=()=>({overflowY:'auto'});
  assert.equal(f.api.searchScroller(f.doc,f.env.win),scroller);
});

test('hidden document can discover without changing its visibility',async()=>{
  const f=fixture();f.doc.visibilityState='hidden';
  const result=await f.api.viewportStep({command_id:12,query:'home gadgets',scroll_iteration:0},f.env);
  assert.equal(result.capture.results_count,2);assert.equal(f.doc.visibilityState,'hidden');
});
