const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

async function reader(options={}) {
  let clock=0, reads=0;
  const updates=[],windows=[],event=()=>({addListener(){}}),url='https://www.tiktok.com/@maker/video/123';
  class FixtureDate extends Date {static now(){return clock;}}
  const context=vm.createContext({URL,AbortSignal,Date:FixtureDate,
    setInterval(){},setTimeout(fn,ms){clock+=ms;queueMicrotask(fn);},
    fetch:async()=>({ok:true,json:async()=>({command:null})}),
    chrome:{runtime:{id:'ext',getManifest:()=>({version:'test'}),onMessage:event(),onInstalled:event(),onStartup:event()},
      alarms:{create:async()=>{},onAlarm:event()},storage:{local:{set:async()=>{},get:async()=>({})}},
      windows:{get:async()=>({state:'minimized'}),update:async(id,data)=>windows.push({id,...data})},
      tabs:{query:async()=>[],get:async()=>({url,status:'complete',windowId:9}),onRemoved:event(),onUpdated:event(),
        update:async(id,data)=>updates.push(data),sendMessage:async()=>{
          reads++;
          const evidence=options.alwaysMissing || reads<3 ? {} : {likes:{value:0},comments_count:{value:1408}};
          return {ok:true,ready:true,diagnostics:{captcha_present:!!options.challenge,document_visibility:options.hidden?'hidden':'visible'},
            video_detail:{video_url:url,video_id:'123',field_evidence:evidence}};
        }}
    }});
  vm.runInContext(fs.readFileSync('extension/pacing.js','utf8')+fs.readFileSync('extension/search_discovery.js','utf8')+fs.readFileSync('extension/background.js','utf8'),context);
  for(let i=0;i<10;i++) await new Promise(resolve=>setImmediate(resolve));
  let result,error;
  try {result=await vm.runInContext('readVideoDetail(7,"https://www.tiktok.com/@maker/video/123")',context);}
  catch(caught){error=caught;}
  return {result,error,clock,reads,updates,windows};
}

test('detail reader waits past label placeholders for two stable numeric samples and preserves zero',async()=>{
  const {result,error,clock,reads,updates,windows}=await reader();
  assert.equal(error,undefined);
  assert.equal(result.field_evidence.likes.value,0);
  assert.equal(result.field_evidence.comments_count.value,1408);
  assert.ok(reads>=4);
  assert.ok(clock<25000);
  assert.equal(updates.length,0,'same video is reused without navigation');
  assert.equal(windows.length,0,'no focus or restore is requested');
});

test('label-only layouts wait the bounded window and return partial evidence without fabricating numbers',async()=>{
  const {result,error,clock}=await reader({alwaysMissing:true});
  assert.equal(error,undefined);
  assert.ok(clock>=25000 && clock<26000);
  assert.equal(result.field_evidence.likes,undefined);
  assert.equal(result.field_evidence.comments_count,undefined);
});

test('a security challenge stops reading rather than returning cached metadata',async()=>{
  const {result,error}=await reader({challenge:true});
  assert.equal(result,undefined);
  assert.match(error.message,/Security challenge/);
});

test('hidden document metadata is read without visibility or focus changes',async()=>{
  const {error,result,windows,updates}=await reader({hidden:true});
  assert.equal(error,undefined);assert.equal(result.video_id,'123');
  assert.equal(windows.length,0);assert.equal(updates.length,0);
});
