const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {domFixture}=require('./dom-fixture.cjs');

function fixture(html=fs.readFileSync('tests/fixtures/tiktok-comments.html','utf8')) {
  const {document,window}=domFixture(html,'https://www.tiktok.com/@maker/video/123');
  let clock=0;const clicks=[];
  class FixtureDate extends Date {static now(){return clock;}}
  for(const button of document.querySelectorAll('button,[role="button"]')) button.click=()=>clicks.push(button.getAttribute('data-e2e'));
  const context=vm.createContext({URL,document,window,Date:FixtureDate,setTimeout(fn,ms){clock+=ms;queueMicrotask(fn);}});
  vm.runInContext(fs.readFileSync('extension/search_results.js','utf8'),context);
  vm.runInContext(fs.readFileSync('extension/comments.js','utf8'),context);
  return {document,window,context,clicks};
}

test('comment rows isolate author/text/likes/timestamp, distinguish visible replies and never click reply/like/composer',async()=>{
  const {context,clicks}=fixture();
  const result=await vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:30})',context);
  assert.equal(result.comments.length,4);
  const [alice,bob,carol,unknown]=result.comments;
  assert.equal(alice.comment_id,'10001');assert.equal(alice.author_username,'@alice');
  assert.equal(alice.text,'How much is the price? Link to buy?');
  assert.equal(alice.likes,1400);assert.equal(alice.likes_raw,'1.4K');assert.equal(alice.timestamp,'2d ago');
  assert.equal(alice.is_reply,false);assert.equal(alice.reply_count,3);
  assert.ok(!alice.raw_visible_text.includes('I bought it'));
  assert.equal(bob.is_reply,true);assert.equal(bob.author_username,'@bob');
  assert.equal(carol.likes,0);assert.equal(unknown.likes,null);assert.equal(unknown.author_username,null);
  assert.equal(result.stop_reason,'no_scrollable_region');
  assert.deepEqual(clicks,[]);
  assert.ok(!JSON.stringify(result).includes('SECRET'));assert.ok(!JSON.stringify(result).includes('$999'));
});

test('bounded target and duplicate IDs do not inflate the sample',async()=>{
  const {context}=fixture('<html><body><div data-e2e="comment-list">'+Array.from({length:120},(_,i)=>`<div data-e2e="comment-level-1" data-comment-id="${Math.floor(i/2)}"><p data-e2e="comment-text">Comment ${Math.floor(i/2)}</p></div>`).join('')+'</div></body></html>');
  const sample=await vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:30})',context);
  assert.equal(sample.comments.length,30);assert.equal(sample.stop_reason,'target_reached');
  assert.equal(new Set(sample.comments.map(item=>item.comment_id)).size,30);
  await assert.rejects(vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:101})',context),/1..100/);
});

test('only the comments scroll region moves; document body and reply controls stay untouched',async()=>{
  const {document,window,context,clicks}=fixture();
  const region=document.querySelector('[data-e2e="comment-list"]');
  region.style.overflowY='auto';region.clientHeight=300;region.scrollHeight=1200;region.scrollTop=0;
  document.body.scrollTop=0;
  const sample=await vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:30})',context);
  assert.ok(sample.scroll_steps>0 && sample.scroll_steps<=20);
  assert.equal(sample.stop_reason,'no_more_loaded');assert.equal(document.body.scrollTop,0);assert.deepEqual(clicks,[]);
});

test('offscreen comments are not read and page identity/security checks prevent unsafe sampling',async()=>{
  const {document,context}=fixture('<html><body><div data-e2e="comment-list"><div data-fixture-offscreen data-e2e="comment-level-1"><p data-e2e="comment-text">OFFSCREEN</p></div></div></body></html>');
  const sample=await vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:30})',context);
  assert.equal(sample.comments.length,0);
  await assert.rejects(vm.runInContext('ProductHunterComments.sampleComments({video_url:"https://www.tiktok.com/@maker/video/999",target_count:30})',context),/identity changed/);
  document.body.innerHTML='<div id="captcha">challenge</div>';
  await assert.rejects(vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:30})',context),/security challenge/);
});

test('real span-level comment shape reads local accessible likes and the timestamp beside Reply without clicking it',async()=>{
  const {context,clicks}=fixture(fs.readFileSync('tests/fixtures/tiktok-comments-live.html','utf8'));
  const sample=await vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:30})',context);
  assert.equal(sample.comments.length,2);
  const [first,second]=sample.comments;
  assert.equal(first.author_username,'@maker');assert.equal(first.text,'Produto legal');
  assert.equal(first.likes,1);assert.equal(first.likes_raw,'1');assert.equal(first.timestamp,'18 h atrás');
  assert.equal(second.author_username,null);assert.equal(second.likes,0);assert.equal(second.timestamp,'1 d atrás');
  assert.ok(!second.text.includes('Responder'));assert.deepEqual(clicks,[]);
});

test('opening comments can click only the exact semantic section toggle',async()=>{
  const {document,context,clicks}=fixture('<html><body><button data-e2e="comment-icon">Comments</button><button data-e2e="like-icon">Like</button><button data-e2e="comment-reply-1">Reply</button></body></html>');
  document.querySelector('[data-e2e="comment-icon"]').click=()=>{
    clicks.push('comment-icon');
    document.body.insertAdjacentHTML('beforeend','<section data-e2e="comment-list"><div data-e2e="comment-level-1"><p data-e2e="comment-text">Visible</p></div></section>');
  };
  const sample=await vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:30})',context);
  assert.equal(sample.comments.length,1);assert.deepEqual(clicks,['comment-icon']);
});

test('absolute sample cap of 100 is enforced even with more DOM rows',async()=>{
  const {context}=fixture('<html><body><div data-e2e="comment-list">'+Array.from({length:150},(_,i)=>`<div data-comment-id="${i}"><p data-e2e="comment-text">Item ${i}</p></div>`).join('')+'</div></body></html>');
  const sample=await vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:100})',context);
  assert.equal(sample.comments.length,100);
});

test('a clipped comment body cannot turn the Reply control or author name into a comment',()=>{
  const {context}=fixture('<html><body><div data-e2e="comment-list"><div><a href="/@maker"><p>Maker Display</p></a><span data-e2e="comment-level-1" hidden>Actual hidden comment</span><span>2 d atrás</span><p data-e2e="comment-reply-1" role="button">Responder</p></div></div></body></html>');
  assert.equal(vm.runInContext('ProductHunterComments.rows(document,window).length',context),0);
});

test('scrolling visibility changes metadata on the same row without creating another comment',async()=>{
  const {document,context}=fixture('<html><body><div data-e2e="comment-list"><div><a href="/@maker" hidden>Maker</a><span data-e2e="comment-level-1">Actual comment</span><p data-e2e="comment-reply-1" role="button">Responder</p></div></div></body></html>');
  const region=document.querySelector('[data-e2e="comment-list"]');
  region.style.overflowY='auto';region.clientHeight=300;region.scrollHeight=1200;
  let top=0;
  Object.defineProperty(region,'scrollTop',{get:()=>top,set:value=>{top=value;document.querySelector('a').hidden=false;}});
  const sample=await vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:30})',context);
  assert.equal(sample.comments.length,1);assert.equal(sample.comments[0].author_username,'@maker');
});

test('React row replacements with the same visible identity are not repeated observations',async()=>{
  const html='<div><a href="/@maker">Maker</a><span data-e2e="comment-level-1">Same comment</span><p data-e2e="comment-reply-1" role="button">Responder</p></div>';
  const {document,context}=fixture('<html><body><div data-e2e="comment-list">'+html+'</div></body></html>');
  const region=document.querySelector('[data-e2e="comment-list"]');
  region.style.overflowY='auto';region.clientHeight=300;region.scrollHeight=1200;
  let top=0;
  Object.defineProperty(region,'scrollTop',{get:()=>top,set:value=>{top=value;region.innerHTML=html;}});
  const sample=await vm.runInContext('ProductHunterComments.sampleComments({video_url:document.location.href,target_count:30})',context);
  assert.equal(sample.comments.length,1);assert.equal(sample.comments[0].text,'Same comment');
});
