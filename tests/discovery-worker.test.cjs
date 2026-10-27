const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');

function setup({challenge=false,networkFailure=false,cancelled=false,alwaysFail=false}={}){
  const stored={},effects=[],posts=[];
  let failure=networkFailure,current={terminal:cancelled,next_iteration:0,document_token:null};
  const context=vm.createContext({URL,console,setTimeout:callback=>callback(),ProductHunterDiscovery:{searchPage:(url,q)=>url===`https://www.tiktok.com/search?q=${q}`},
    focusWindow:async()=>effects.push('focus'),updateVisualTab:async()=>effects.push('activate'),
    request:async(path,body)=>{
      if(path.includes('/control?'))return {...current};
      posts.push({path,body});
      if(path.endsWith('/step')){if(failure||alwaysFail){failure=false;throw new Error('transport failure');}current={...current,terminal:true,next_iteration:1};return {...current};}
      if(path.endsWith('/finish')){current={...current,terminal:true};return {...current};}
      return {ok:true};
    },chrome:{runtime:{id:'ext'},windows:{get:async()=>({state:'normal'})},
      storage:{local:{get:async key=>({[key]:stored[key]}),set:async value=>Object.assign(stored,value),remove:async key=>{delete stored[key];}}},
      tabs:{get:async()=>({id:1,windowId:1,url:'https://www.tiktok.com/search?q=home gadgets'}),
        sendMessage:async()=>{effects.push('viewport');return challenge?{ok:false,challenge:true}:{ok:true,document_token:'doc',dom_card_count:1,capture:{query:'home gadgets',results:[]}};}}
    }});
  vm.runInContext(fs.readFileSync('extension/discovery_worker.js','utf8'),context);
  return {stored,effects,posts,run:()=>context.ProductHunterDiscoveryWorker.run(1,{id:1,query:'home gadgets'})};
}

test('worker persists viewport before transport and retries exactly without another viewport',async()=>{
  const f=setup({networkFailure:true});
  await assert.rejects(f.run(),/transport failure/);
  assert.ok(f.stored.pendingDiscoveryStep);
  assert.ok(f.stored.activeDiscovery);
  await f.run();
  assert.equal(f.effects.filter(e=>e==='viewport').length,1);
  assert.equal(f.stored.pendingDiscoveryStep,undefined);
  assert.equal(f.stored.activeDiscovery,undefined);
  assert.deepEqual(f.posts[0].body,f.posts[1].body);
});


test('terminal cancellation performs no further browser operation',async()=>{
  const f=setup({cancelled:true});await f.run();assert.deepEqual(f.effects,[]);assert.deepEqual(f.posts,[]);
});

test('security challenge finishes immediately without submitting a viewport',async()=>{
  const f=setup({challenge:true});await f.run();
  assert.equal(f.posts.length,1);assert.equal(f.posts[0].body.stop_reason,'security_challenge');
  assert.equal(f.stored.activeDiscovery,undefined);
});

test('transport retry budget stops discovery without scrolling another viewport',async()=>{
  const f=setup({alwaysFail:true});
  await assert.rejects(f.run(),/transport failure/);
  await assert.rejects(f.run(),/transport failure/);
  await f.run();
  assert.equal(f.effects.filter(e=>e==='viewport').length,1);
  assert.equal(f.posts.at(-1).body.stop_reason,'error');
  assert.equal(f.stored.activeDiscovery,undefined);
});
