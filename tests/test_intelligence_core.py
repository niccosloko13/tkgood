import json
import sqlite3
import sys
from pathlib import Path
import pytest
from app import intelligence_core as core,intelligence_jobs as jobs
from app.intelligence_decisions import decide,same_product
from app.intelligence_embeddings import ResourceGovernor,ResourceBusy,OpenCLIPProvider,ModelUnavailable
from app.intelligence_index import ProductIndex
from test_product_detection import library,seed


@pytest.fixture
def con(library):
    with library.connect() as c:
        seed(c,None);core.migrate(c);yield c


def strong(**changes):
    return dict(name='Mini PVA Mop',visual_available=True,visual_supported=True,text_supported=True,
                independent_listings=2,specific_terms=['pva'],**changes)


@pytest.mark.parametrize('e,status,reason',[
    ({},'UNRESOLVED','UNRESOLVED_NO_VISUAL'),
    ({'visual_available':True},'UNRESOLVED','UNRESOLVED_GENERIC_TEXT'),
    ({'visual_available':True,'name':'Mini Mop'},'UNRESOLVED','UNRESOLVED_INSUFFICIENT_EVIDENCE'),
    ({'visual_available':True,'name':'Mini Mop','visual_supported':True},'REVIEW','REVIEW_INSUFFICIENT_CORROBORATION'),
    (strong(),'AUTO','AUTO_STRONG_MULTISOURCE_MATCH'),
    (strong(conflicts=['variant']),'REVIEW','REVIEW_POSSIBLE_VARIANT'),
    (strong(conflicts=['contradiction']),'REVIEW','REVIEW_CONFLICTING_VISUAL_RESULTS'),
    (strong(retrieval_conflict=True),'REVIEW','REVIEW_POSSIBLE_VARIANT')])
def test_central_decisions(e,status,reason):
    r=decide(e);assert (r['status'],r['reason_code'])==(status,reason)


def test_similarity_not_identity_and_conflict_caps():
    e={'image_similarity':1.0,'text_similarity':1.0}
    assert same_product(e)=='possible_same_product'
    e.update(resolver={'identity_score':90,'semantic_result':'possible_same_product'},brand_model_match=True,specific_terms=['pva'],independent_listings=2)
    assert same_product(e)=='same_product_likely'
    assert same_product({**e,'conflicts':['variant']})=='possible_same_product'
    assert same_product({**e,'conflicts':['model']})=='different_product'
    assert same_product({})=='insufficient'


def test_jobs_dedup_idempotency_and_ownership(con):
    a=jobs.enqueue(con,'identity',1,{'x':1});b=jobs.enqueue(con,'identity',1,{'x':1});assert a==b
    j=jobs.claim(con);assert j['attempt_count']==1
    assert jobs.claim(con) is None
    jobs.finish(con,j,status='unresolved',reason='NO_DATA')
    with pytest.raises(ValueError):jobs.finish(con,j)
    assert jobs.enqueue(con,'identity',1,{'x':2})!=a


def test_superseded_input_does_not_process_stale_work(con):
    old=jobs.enqueue(con,'identity',1,{'input':'old'})
    current=jobs.enqueue(con,'identity',1,{'input':'current'})
    assert jobs.claim(con)['id']==current
    assert con.execute('SELECT status FROM intelligence_jobs WHERE id=?',(old,)).fetchone()[0]=='superseded'


@pytest.mark.parametrize('failure,status',[('SECURITY_BLOCK','blocked'),('PERMANENT','dead-letter'),('INSUFFICIENT_DATA','unresolved')])
def test_failures_do_not_stall_next_job(con,failure,status):
    jobs.enqueue(con,'identity',1,{'x':1});jobs.enqueue(con,'identity',2,{'x':2})
    j=jobs.claim(con);jobs.finish(con,j,failure=failure)
    assert con.execute('SELECT status FROM intelligence_jobs WHERE id=?',(j['id'],)).fetchone()[0]==status
    next_job=jobs.claim(con);assert next_job['target']=='2'
    if failure=='SECURITY_BLOCK':
        assert jobs.blocked_jobs(con)[0]['recoverable'] is False
        assert jobs.claim(con) is None


def test_transient_retry_bounded_and_expired_leases(con):
    jobs.enqueue(con,'identity',1,{})
    for count in range(3):
        j=jobs.claim(con);assert j['attempt_count']==count+1
        jobs.finish(con,j,failure='TRANSIENT')
        con.execute("UPDATE intelligence_jobs SET available_at='2000-01-01'")
    assert jobs.claim(con) is None
    assert jobs.blocked_jobs(con)[0]['status']=='dead-letter'
    jobs.enqueue(con,'identity',2,{})
    j=jobs.claim(con)
    con.execute("UPDATE intelligence_jobs SET lease_until='2000-01-01' WHERE id=?",(j['id'],))
    assert jobs.claim(con)['attempt_count']==2
    with pytest.raises(ValueError):jobs.finish(con,j)


def test_atomic_swap_failure_keeps_old_and_version_checks(tmp_path):
    index=ProductIndex(tmp_path)
    old=index.rebuild([{'product_id':'approved-A','vector':[1,0,0]}],'v1',3)
    def fail(_):raise ValueError('disk validation failure')
    with pytest.raises(ValueError):index.rebuild([{'product_id':'approved-B','vector':[0,1,0]}],'v1',3,fail)
    assert index.metadata()['generation']==old['generation']
    result=index.search([1,0,0],'v1');assert result[0]['product_id']=='approved-A'
    assert result[0]['similarity']==pytest.approx(1)
    with pytest.raises(ValueError):index.search([1,0,0],'different-version')
    with pytest.raises(ValueError):index.rebuild([{'product_id':'bad','vector':[float('nan'),0,0]}],'v1',3)


def test_index_top3_and_checksum_before_deserialization(tmp_path):
    index=ProductIndex(tmp_path)
    index.rebuild([{'product_id':str(i),'vector':[1,i/10,0]} for i in range(5)],'v',3)
    assert len(index.search([1,0,0],'v'))==3
    m=index.metadata();(tmp_path/m['generation']/'index.faiss').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):index.search([1,0,0],'v')


def test_empty_index_is_valid_not_fake_data(tmp_path):
    index=ProductIndex(tmp_path);index.rebuild([],'v',3)
    assert index.search([1,0,0],'v')==[]


def test_resource_governor_pressure_and_concurrency(monkeypatch,tmp_path):
    from app import intelligence_embeddings as e
    monkeypatch.setattr(e,'ROOT',tmp_path)
    g=ResourceGovernor();monkeypatch.setattr(g,'state',lambda:{'allowed':False})
    with pytest.raises(ResourceBusy):
        with g.reserve():pass
    monkeypatch.setattr(g,'state',lambda:{'allowed':True})
    with g.reserve():
        with pytest.raises(ResourceBusy):
            with g.reserve():pass


def test_cache_reuses_version_kind_hash_without_loading_model(con,monkeypatch):
    import hashlib
    p=OpenCLIPProvider()
    monkeypatch.setattr(OpenCLIPProvider,'version',property(lambda self:'pinned-test-v'))
    monkeypatch.setattr(p,'_load',lambda:pytest.fail('Model loaded on cache hit'))
    con.execute('INSERT INTO intelligence_embeddings VALUES (?,?,?,?,?)',('pinned-test-v','text',hashlib.sha256(b'caption').hexdigest(),'[1,0]',jobs.now()))
    assert p.embed(con,'text','caption')==[1,0]
    assert p.model is None and p.cache_hits==1
    assert con.execute('SELECT hits FROM intelligence_cache_stats').fetchone()[0]==1


def test_model_missing_is_explicit_and_lazy(tmp_path,monkeypatch):
    from app import intelligence_embeddings as e
    monkeypatch.setattr(e,'ROOT',tmp_path)
    p=OpenCLIPProvider();assert p.model is None
    with pytest.raises(ModelUnavailable):_ = p.version


def test_core_is_gold_isolated_and_no_tiktok_or_candidate_mutation(con,monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket,'connect',lambda *a:pytest.fail('Network access forbidden'))
    before=[tuple(r) for r in con.execute('SELECT * FROM product_candidates')]
    first=core.identify(con,1)
    # SQLite authorizer detects any Gold access even via indirect helpers.
    def authorize(action,a,b,db,trigger):
        if a and a.startswith('gold_'):return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    con.set_authorizer(authorize)
    second=core.identify(con,1)
    assert first['id']==second['id'] and second['status']=='UNRESOLVED'
    assert [tuple(r) for r in con.execute('SELECT * FROM product_candidates')]==before
    assert con.execute('SELECT count(*) FROM intelligence_entities').fetchone()[0]==0
    con.set_authorizer(lambda *args:sqlite3.SQLITE_OK)


def test_entity_gate_and_explicit_human_review(con,monkeypatch):
    monkeypatch.setattr(core,'evidence_for',lambda _:strong(conflicts=['visual_names'],alternatives=['Window Sponge'],source_ids={'visual':[],'comments':[],'web':[]}))
    r=core.identify(con,1);assert r['status']=='REVIEW'
    with pytest.raises(ValueError):core._approve(con,r['id'],'Mini PVA Mop','AUTO')
    with pytest.raises(ValueError):core._approve(con,r['id'],'Mini PVA Mop','human_confirmed')
    result=core.review(con,r['id'],'confirm','Mini PVA Mop')
    assert result['product_id'] and not result['gold_changed'] and not result['candidate_changed']
    core.review(con,r['id'],'confirm','Mini PVA Mop')
    assert con.execute('SELECT count(*) FROM intelligence_entities').fetchone()[0]==1
    assert con.execute('SELECT count(*) FROM intelligence_reviews').fetchone()[0]==1
    with pytest.raises(ValueError):core.review(con,r['id'],'confirm','not observed')


def test_review_stale_evidence_refused(con,monkeypatch):
    monkeypatch.setattr(core,'evidence_for',lambda _:strong(conflicts=['variant']))
    r=core.identify(con,1)
    con.execute("UPDATE videos SET caption='different input' WHERE id=1")
    with pytest.raises(ValueError,match='Evidence changed'):core.review(con,r['id'],'confirm','Mini PVA Mop')


def test_evaluation_has_no_false_merge_claims_and_no_label_mutation(con):
    from app.intelligence_evaluation import evaluate
    before=[tuple(r) for r in con.execute('SELECT * FROM gold_video_labels')]
    r=evaluate(con)
    assert r['false_merge_rate'] is None and r['auto_decision_accuracy'] is None
    assert before==[tuple(r) for r in con.execute('SELECT * FROM gold_video_labels')]


def test_temporal_signals_no_interpolation(con):
    r=core.temporal_signals(con)
    assert r['topics']['status']=='insufficient_history'
    assert len(r['series'])==1
    assert r['series'][0]['comments_observed'] is None


def test_only_local_job_types(con):
    with pytest.raises(ValueError):jobs.enqueue(con,'SEARCH','tiktok',{})


def test_no_model_import_on_core_import():
    import subprocess
    code="import sys; import app.intelligence_core; import app.intelligence_api; assert not any(x in sys.modules for x in ['torch','open_clip','faiss'])"
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_weak_cosine_never_adds_review_pressure():
    assert same_product({'image_similarity':.05,'text_similarity':.1})=='insufficient'


def test_local_model_adapter_cache_miss_normalizes_and_reuses(con,monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    import hashlib
    calls=[]
    class Vector:
        def cpu(self):return self
        def float(self):return self
        def tolist(self):return [1.,0.]
    class Model:
        def encode_text(self,text,normalize):
            calls.append((text,normalize));return [Vector()]
    p=OpenCLIPProvider()
    monkeypatch.setattr(OpenCLIPProvider,'version',property(lambda self:'test-model-v2'))
    def load():p.model=Model();p.tokenizer=lambda x:x;p.loaded_version='test-model-v2'
    monkeypatch.setattr(p,'_load',load)
    monkeypatch.setattr(ResourceGovernor,'reserve',lambda _:nullcontext())
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(inference_mode=nullcontext))
    assert p.embed(con,'text','real observation input')==[1.,0.]
    assert p.embed(con,'text','real observation input')==[1.,0.]
    assert calls==[(['real observation input'],True)]
    assert p.cache_hits==1
    stored=con.execute('SELECT * FROM intelligence_embeddings').fetchone()
    assert stored['sha256']==hashlib.sha256(b'real observation input').hexdigest()


def test_pointer_swap_failure_retains_active_index(tmp_path,monkeypatch):
    import app.intelligence_index as module
    index=ProductIndex(tmp_path);old=index.rebuild([{'product_id':'A','vector':[1,0]}],'v',2)
    replace=module.os.replace
    def interrupted(source,destination):
        if Path(destination).name=='current.json':raise OSError('interrupted pointer publication')
        return replace(source,destination)
    monkeypatch.setattr(module.os,'replace',interrupted)
    with pytest.raises(OSError):index.rebuild([{'product_id':'B','vector':[0,1]}],'v',2)
    assert index.metadata()==old
    assert index.search([1,0],'v')[0]['product_id']=='A'


def test_event_reconciles_once_without_model_and_keeps_gold_private(con):
    def authorize(action,a,b,db,trigger):
        return sqlite3.SQLITE_DENY if a and a.startswith('gold_') else sqlite3.SQLITE_OK
    con.set_authorizer(authorize)
    jid=core.evidence_changed(con,1)
    assert core.evidence_changed(con,1)==jid
    assert con.execute('SELECT count(*) FROM intelligence_decisions').fetchone()[0]==1
    assert con.execute('SELECT status FROM intelligence_jobs').fetchone()[0]=='unresolved'
    con.set_authorizer(lambda *args:sqlite3.SQLITE_OK)


def test_light_lane_not_stalled_by_heavy_resource_job(con):
    jobs.enqueue(con,'identity',1,{'with_embeddings':True})
    jobs.enqueue(con,'identity',1,{'with_embeddings':False})
    results=core.process(con,with_embeddings=False)
    assert len(results)==1
    assert con.execute("SELECT status FROM intelligence_jobs WHERE json_extract(payload_json,'$.with_embeddings')=1").fetchone()[0]=='queued'


def test_resource_pressure_pauses_heavy_batch_without_burning_all_attempts(con,monkeypatch):
    jobs.enqueue(con,'identity',1,{'with_embeddings':True})
    jobs.enqueue(con,'identity',2,{'with_embeddings':True})
    monkeypatch.setattr(core,'identify',lambda *args,**kwargs:(_ for _ in ()).throw(ResourceBusy('RESOURCE_PRESSURE')))
    core.process(con,with_embeddings=True)
    assert [r[0] for r in con.execute('SELECT attempt_count FROM intelligence_jobs ORDER BY id')]==[1,0]


def test_permanent_custom_reason_is_not_recoverable(con):
    jobs.enqueue(con,'identity',1,{})
    j=jobs.claim(con);jobs.finish(con,j,failure='PERMANENT',reason='INVALID_LOCAL_INPUT')
    assert jobs.blocked_jobs(con)[0]['recoverable'] is False


def test_core_local_write_rejects_cross_site():
    from starlette.requests import Request
    from fastapi import HTTPException
    from app.intelligence_api import local_write
    r=Request({'type':'http','scheme':'http','server':('127.0.0.1',8000),'path':'/','headers':[(b'origin',b'https://attacker.invalid')],'query_string':b''})
    with pytest.raises(HTTPException) as e:local_write(r)
    assert e.value.status_code==403
