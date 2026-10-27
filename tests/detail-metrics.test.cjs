const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {domFixture}=require('./dom-fixture.cjs');

function extract(html,setup=()=>{}) {
  const {document,window}=domFixture(html,'https://www.tiktok.com/@maker/video/123');
  document.readyState='complete'; setup(document,window);
  const context=vm.createContext({document,window,URL});
  vm.runInContext(fs.readFileSync('extension/search_results.js','utf8'),context);
  vm.runInContext(fs.readFileSync('extension/video_detail.js','utf8'),context);
  return JSON.parse(JSON.stringify(vm.runInContext('ProductHunterDetail.extractVideoDetail()',context)));
}
const wrap=content=>`<html><body><article><a data-e2e="browse-username" href="/@maker">Maker</a><p data-e2e="video-desc">Tool</p>${content}</article></body></html>`;

test('visible action aria labels and adjacent spans normalize into separate metric values',()=>{
  const {video_detail:d}=extract(fs.readFileSync('tests/fixtures/tiktok-detail-metrics.html','utf8'));
  assert.equal(d.views,83100);
  const expected={likes:[31200,'31.2K','aria_label',.95],comments_count:[2251,'2251','action_text',.94],
    shares:[21400,'21.4K','aria_label',.95],favorites:[1400000,'1,4M','aria_label',.95]};
  for (const [name,[value,raw,method,confidence]] of Object.entries(expected)) {
    assert.equal(d.field_evidence[name].value,value,name);
    assert.equal(d.field_evidence[name].raw_value,raw);
    assert.equal(d.field_evidence[name].source,'video_detail');
    assert.equal(d.field_evidence[name].method,method);
    assert.equal(d.field_evidence[name].confidence,confidence);
    assert.equal(d[name],raw);
  }
  assert.ok(d.raw_visible_text.includes('Compartilhar'));
  assert.ok(!d.raw_visible_text.includes('COMMENT BODY'));
  assert.ok(!d.raw_visible_text.includes('999999'));
});

test('actual label-only shape never becomes zero or borrows the share count',()=>{
  const {video_detail:d}=extract(wrap('<section><div data-e2e="like-icon" role="button" aria-label="Curtir vídeo&#10; curtidas"><button></button><strong data-e2e="like-count">Curtida</strong></div><div data-e2e="comment-icon" role="button" aria-label="Ler ou adicionar comentários&#10; comentários"><strong data-e2e="comment-count">Comentários</strong></div><div data-e2e="share-icon" role="button" aria-label="Compartilhar vídeo&#10;21.4K compartilhamentos"><strong data-e2e="share-count">Compartilhar</strong></div></section>'));
  assert.equal(d.likes,null);
  assert.equal(d.comments_count,null);
  assert.equal(d.views,null);
  assert.equal(d.field_evidence.likes,undefined);
  assert.equal(d.field_evidence.comments_count,undefined);
  assert.equal(d.field_evidence.shares.value,21400);
});

test('hidden/offscreen numbers and attributes do not become visible metrics',()=>{
  const {video_detail:d}=extract(wrap('<div data-e2e="like-icon"><strong data-e2e="like-count">Curtida</strong><span hidden>31.2K</span></div><div data-fixture-offscreen data-e2e="comment-icon" aria-label="2251 comments"><strong data-e2e="comment-count">2251</strong></div><div data-e2e="favorite-icon" data-count="10000"><strong data-e2e="favorite-count">Favoritos</strong></div>'));
  assert.equal(d.likes,null); assert.equal(d.comments_count,null); assert.equal(d.favorites,null);
  assert.ok(!d.raw_visible_text.includes('31.2K'));
  assert.ok(!d.raw_visible_text.includes('10000'));
});

test('semantic counts have precedence over accessible alternatives; zero is a valid visible count',()=>{
  const {video_detail:d}=extract(wrap('<div data-e2e="like-icon" aria-label="900 likes"><strong data-e2e="like-count">0</strong></div><div data-e2e="comment-icon" aria-label="555 comments"><strong data-e2e="comment-count">2B</strong></div>'));
  assert.equal(d.field_evidence.likes.value,0);
  assert.equal(d.field_evidence.likes.confidence,.98);
  assert.equal(d.field_evidence.comments_count.value,2000000000);
});

test('ambiguous adjacent counts and wrong metric labels are rejected',()=>{
  const {video_detail:d,diagnostics}=extract(wrap('<div data-e2e="like-icon" aria-label="123 comments"><strong data-e2e="like-count">Curtida</strong><span>100</span><span>200</span></div><div data-e2e="comment-icon" aria-label="31.2K likes"><strong data-e2e="comment-count">Comentários</strong></div>'));
  assert.equal(d.likes,null); assert.equal(d.comments_count,null);
  assert.equal(diagnostics.metrics.likes.ambiguous,true);
});

test('view labels cannot be interpreted as likes by the shared K/M/B parser',()=>{
  const {video_detail:d}=extract(wrap('<div data-e2e="like-icon" aria-label="83.1K views"><strong data-e2e="like-count">Curtida</strong></div><div data-e2e="comment-icon" aria-label="31.2K curtidas"><strong data-e2e="comment-count">Comentários</strong></div>'));
  assert.equal(d.likes,null); assert.equal(d.comments_count,null);
});

test('unrecognized numeric format keeps raw evidence and a null normalized value',()=>{
  const {video_detail:d}=extract(wrap('<strong data-e2e="like-count">12Q</strong><strong data-e2e="video-views">1.2</strong>'));
  assert.equal(d.likes,'12Q');
  assert.equal(d.field_evidence.likes.value,null);
  assert.equal(d.field_evidence.likes.confidence,0);
  assert.equal(d.views_raw,'1.2');
  assert.equal(d.field_evidence.views.value,null);
});

test('CSS-generated rendered numeric content is accepted only on a visible local metric element',()=>{
  const {video_detail:d}=extract(wrap('<div data-e2e="like-icon"><strong data-e2e="like-count">Curtida</strong></div>'),(document,window)=>{
    const computed=window.getComputedStyle;
    window.getComputedStyle=(node,pseudo)=>({...computed(node),content:pseudo==='::before' && node.getAttribute('data-e2e')==='like-count'?'"83.1K"':'none'});
  });
  assert.equal(d.field_evidence.likes.value,83100);
  assert.equal(d.field_evidence.likes.method,'generated_content');
});
