const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {domFixture}=require('./dom-fixture.cjs');
const {extractCreatorProfile,normalizeCount,profileUrl}=require('../extension/creator_profile.js');
const html=fs.readFileSync('tests/fixtures/tiktok-creator-profile.html','utf8');
function fixture(value=html,url='https://www.tiktok.com/@maker'){
  const dom=domFixture(value,url);dom.document.readyState='complete';return dom;
}

test('profile header isolates public semantic values and provenance without any engagement',()=>{
  const {document,window}=fixture();let clicks=0;window.HTMLElement.prototype.click=()=>clicks++;
  const result=extractCreatorProfile(document,window);assert.equal(result.ready,true);
  const p=result.creator_profile;assert.equal(p.username,'@maker');assert.equal(p.followers,31200);assert.equal(p.total_likes,1400000);
  assert.equal(p.following,123);assert.equal(p.video_count,80);assert.equal(p.display_name,'Maker Studio');
  assert.equal(p.field_evidence.followers.raw_value,'31.2K');assert.equal(p.field_evidence.followers.normalized_value,31200);
  assert.equal(p.field_evidence.followers.source,'creator_profile');assert.equal(p.field_evidence.followers.confidence,.98);
  assert.equal(p.links.length,1);assert.equal(p.links[0].label,'My shop');
  for(const bad of ['999M','WRONG','PRIVATE','Follow','Message'])assert.ok(!p.raw_visible_text.includes(bad));
  assert.equal(clicks,0);
});

test('missing bio, link and offscreen fields stay null rather than using surrounding text',()=>{
  const {document,window}=fixture();document.querySelector('[data-e2e="user-bio"]').remove();document.querySelector('[data-e2e="user-link"]').remove();
  document.querySelector('[data-e2e="user-subtitle"]').hidden=true;
  const p=extractCreatorProfile(document,window).creator_profile;
  assert.equal(p.bio,null);assert.equal(p.external_link,null);assert.equal(p.display_name,null);assert.deepEqual(p.links,[]);
});

test('TikTok empty-bio placeholders are audit evidence, not a fabricated biography',()=>{
  for(const label of ['Ainda sem descrição.','No bio yet.']){
    const {document,window}=fixture();document.querySelector('[data-e2e="user-bio"]').textContent=label;
    const profile=extractCreatorProfile(document,window).creator_profile;
    assert.equal(profile.bio,null);assert.equal(profile.field_evidence.bio,undefined);
    assert.ok(profile.raw_visible_text.includes(label));
  }
});

test('logical profile header includes bio/avatar siblings without crossing into the video grid',()=>{
  const {document,window}=fixture('<html><body><div><section><div><h1 data-e2e="user-title">maker</h1><strong data-e2e="followers-count">9000</strong><strong data-e2e="likes-count">1M</strong></div><p data-e2e="user-bio">Sibling bio</p><img data-e2e="user-avatar" src="https://images.example/avatar.png"></section><div><a href="/@other/video/123">WRONG BIO</a></div></div></body></html>');
  const profile=extractCreatorProfile(document,window).creator_profile;
  assert.equal(profile.bio,'Sibling bio');assert.equal(profile.avatar_url,'https://images.example/avatar.png');
  assert.ok(!profile.raw_visible_text.includes('WRONG'));
});

test('profile count normalization is exact and preserves ambiguous raw values',()=>{
  for(const [raw,value] of [['31.2K',31200],['31,2K',31200],['1.4M',1400000],['2B',2000000000],['0',0],['9999',9999],['1,234',null],['1.234',null],['Followers',null],['1.2',null]])assert.equal(normalizeCount(raw),value,raw);
  const {document,window}=fixture();document.querySelector('header [data-e2e="followers-count"]').textContent='1,234';
  const p=extractCreatorProfile(document,window).creator_profile;assert.equal(p.followers,null);assert.equal(p.field_evidence.followers.raw_value,'1,234');
});

test('swapped live title/subtitle still requires a visible username matching the requested route',()=>{
  const {document,window}=fixture();document.querySelector('[data-e2e="user-title"]').textContent='Maker Studio';document.querySelector('[data-e2e="user-subtitle"]').textContent='maker';
  const p=extractCreatorProfile(document,window).creator_profile;
  assert.equal(p.username,'@maker');assert.equal(p.display_name,'Maker Studio');
  assert.equal(p.field_evidence.username.raw_value,'maker');
});

test('visible header avatar fallback and bio redirects preserve public URLs without following any link',()=>{
  const {document,window}=fixture();const image=document.querySelector('img');image.removeAttribute('data-e2e');image.removeAttribute('alt');
  image.getBoundingClientRect=()=>({left:10,right:90,top:10,bottom:90,width:80,height:80});
  const link=document.querySelector('[data-e2e="user-link"]');link.setAttribute('href','https://www.tiktok.com/link/v2?target=https%3A%2F%2Fshop.example');
  const p=extractCreatorProfile(document,window).creator_profile;
  assert.equal(p.avatar_url,'https://images.example/avatar.png');assert.equal(p.field_evidence.avatar_url.method,'visible_header_image');assert.equal(p.field_evidence.avatar_url.confidence,.90);
  assert.equal(p.external_link,link.getAttribute('href'));assert.equal(p.links[0].url,link.getAttribute('href'));
  image.removeAttribute('src');assert.equal(extractCreatorProfile(document,window).creator_profile.avatar_url,null);
  link.setAttribute('href','https://shop.example?access_token=private');assert.equal(extractCreatorProfile(document,window).creator_profile.external_link,null);
});

test('micro/mega fixtures, canonical routes and challenge/mismatched identity guards',()=>{
  for(const [raw,value] of [['9000',9000],['2M',2000000]]){
    const {document,window}=fixture();document.querySelector('header [data-e2e="followers-count"]').textContent=raw;
    assert.equal(extractCreatorProfile(document,window).creator_profile.followers,value);
  }
  assert.equal(profileUrl('https://tiktok.com/@MaKer/?lang=en#x'),'https://www.tiktok.com/@maker');
  for(const url of ['https://evil.test/@maker','https://www.tiktok.com/@maker/video/1','https://www.tiktok.com/login','https://www.tiktok.com:444/@maker'])assert.equal(profileUrl(url),null);
  const {document,window}=fixture();document.location.href='https://www.tiktok.com/@different';assert.equal(extractCreatorProfile(document,window).ready,false);
  document.location.href='https://www.tiktok.com/@maker';const challenge=document.createElement('div');challenge.id='captcha-verify';document.body.appendChild(challenge);assert.equal(extractCreatorProfile(document,window).challenge,true);
});

test('profile worker waits for asynchronous visible counts, returns only to the related library video',async()=>{
  let clock=0,reads=0,current='https://www.tiktok.com/@maker/video/123';const updates=[];
  class Clock extends Date {static now(){return clock;}}
  const event=()=>({addListener(){}}),context=vm.createContext({URL,AbortSignal,Date:Clock,setInterval(){},setTimeout(fn,ms){clock+=ms;queueMicrotask(fn);},
    fetch:async()=>({ok:true,json:async()=>({command:null})}),chrome:{runtime:{id:'ext',getManifest:()=>({version:'test'}),onMessage:event(),onInstalled:event(),onStartup:event()},alarms:{create:async()=>{},onAlarm:event()},storage:{local:{set:async()=>{},get:async()=>({})}},
      tabs:{query:async()=>[],onRemoved:event(),onUpdated:event(),get:async()=>({url:current,status:'complete'}),update:async(id,value)=>{updates.push(value);if(value.url)current=value.url;},sendMessage:async()=>{reads++;return {ok:true,ready:true,creator_profile:{profile_url:'https://www.tiktok.com/@maker',followers:reads<4?null:31200,total_likes:reads<4?null:1400000,bio:reads<4?null:'Loaded bio',display_name:'Maker'}};}}}});
  vm.runInContext(fs.readFileSync('extension/pacing.js','utf8')+fs.readFileSync('extension/search_discovery.js','utf8')+fs.readFileSync('extension/background.js','utf8'),context);
  const result=await vm.runInContext('readCreatorProfile(1,"https://www.tiktok.com/@maker","https://www.tiktok.com/@maker/video/123")',context);
  assert.equal(result.followers,31200);assert.equal(result.bio,'Loaded bio');assert.ok(clock>=5000);
  assert.equal(updates[0].url,'https://www.tiktok.com/@maker');assert.equal(updates.at(-1).url,'https://www.tiktok.com/@maker/video/123');
  assert.ok(reads>=4);
});

test('profile timeout returns to its video, while a challenge stops and remains for human intervention',async()=>{
  for(const challenge of [false,true]){
    let clock=0,current='https://www.tiktok.com/@maker/video/123';const updates=[];
    class Clock extends Date{static now(){return clock;}}
    const event=()=>({addListener(){}}),context=vm.createContext({URL,AbortSignal,Date:Clock,setInterval(){},setTimeout(fn,ms){clock+=ms;queueMicrotask(fn);},
      fetch:async()=>({ok:true,json:async()=>({command:null})}),chrome:{runtime:{id:'ext',getManifest:()=>({version:'test'}),onMessage:event(),onInstalled:event(),onStartup:event()},alarms:{create:async()=>{},onAlarm:event()},storage:{local:{set:async()=>{},get:async()=>({})}},
        tabs:{query:async()=>[],onRemoved:event(),onUpdated:event(),get:async()=>({url:current,status:'complete'}),update:async(id,value)=>{updates.push(value);if(value.url)current=value.url;},sendMessage:async()=>({ok:true,ready:false,challenge,diagnostics:['No rendered profile']})}}});
    vm.runInContext(fs.readFileSync('extension/pacing.js','utf8')+fs.readFileSync('extension/search_discovery.js','utf8')+fs.readFileSync('extension/background.js','utf8'),context);
    await assert.rejects(vm.runInContext('readCreatorProfile(1,"https://www.tiktok.com/@maker","https://www.tiktok.com/@maker/video/123")',context),challenge?/human intervention/:/not ready/);
    assert.equal(updates.length,challenge?1:2);
    assert.equal(current,challenge?'https://www.tiktok.com/@maker':'https://www.tiktok.com/@maker/video/123');
    if(!challenge)assert.ok(clock>=30000&&clock<31000);
    await assert.rejects(vm.runInContext('readCreatorProfile(1,"https://evil.test/@maker","https://www.tiktok.com/@maker/video/123")',context),/Invalid/);
  }
});
