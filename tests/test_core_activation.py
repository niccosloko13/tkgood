import json
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from app import intelligence_core as core,intelligence_jobs as jobs
from app.intelligence_decisions import decide,specificity
from app.intelligence_embeddings import ResourceGovernor,OpenCLIPProvider
from app.intelligence_index import ProductIndex
from app.comments import consumer_signals
from test_product_detection import library,seed


def item(caption='',names=(),comments=(),unresolved=(),image=False):
    return {'caption':caption,'candidates':[{'id':i+1,'canonical_name':n,'recurrence':1} for i,n in enumerate(names)],
            'comments':list(comments),'unresolved':[{'raw_phrase':n} for n in unresolved],
            'proposals':[],'image':{'status':'available' if image else 'visual_unavailable'}}


@pytest.mark.parametrize('phrase',['mini vacuum cleaner','soap dispenser','dish brush','motion sensor light','burger patty maker','window cleaner'])
def test_specific_compounds_without_gold_or_fixed_full_name_list(phrase):
    assert specificity(phrase)['specific']


@pytest.mark.parametrize('phrase',['gadget','product','tool','thing','cleaner','device','home find'])
def test_generic_heads_do_not_become_identity(phrase):
    assert not specificity(phrase)['specific']


def test_video_three_text_only_composition():
    evidence=core.evidence_for(item('Soap dispenser and dish brush in one',('Soap dispenser','dish brush')))
    result=decide(evidence)
    assert result['status']=='REVIEW' and result['reason_code']=='REVIEW_TEXT_COMPOSITE_PRODUCT'
    assert evidence['text_supported'] and evidence['composition'] and not evidence['visual_available']


def test_video_one_specific_comment_hypothesis_not_confirmation():
    comments=[{'id':1,'text':'vacuum cleaner','author_username':'a'}, {'id':2,'text':'Mini Vacuum Cleaner Price? very useful','author_username':'b'}]
    evidence=core.evidence_for(item('Easy to remove the stains #gadgets',comments=comments,unresolved=('vacuum cleaner','Mini Vacuum Cleaner'),image=True))
    assert evidence['name']=='Mini Vacuum Cleaner'
    assert not evidence['generic_text'] and evidence['text_supported']
    assert evidence['visual_flow_status']=='LENS_ASSISTED_REQUIRED'
    assert decide(evidence)['status']=='REVIEW'
    assert not evidence['visual_supported']


def test_strong_text_auto_is_reachable_without_visual_and_without_similarity():
    comments=[{'id':1,'text':'soap dispenser works','author_username':'a'},{'id':2,'text':'soap dispenser is useful','author_username':'b'}]
    data=item('Soap dispenser',('Soap dispenser',),comments)
    data['candidates'][0]['recurrence']=2
    result=decide(core.evidence_for(data))
    assert result['status']=='AUTO' and result['reason_code']=='AUTO_STRONG_TEXT_IDENTITY'
    assert decide({**core.evidence_for(data),'conflicts':['variant']})['status']=='REVIEW'


def test_negative_identity_comments_cannot_auto_confirm_a_literal_name():
    data=item('Soap dispenser',('Soap dispenser',),[{'id':1,'text':'not a soap dispenser','author_username':'a'},{'id':2,'text':'this is not soap dispenser','author_username':'b'}])
    data['candidates'][0]['recurrence']=3
    evidence=core.evidence_for(data)
    assert evidence['compatible_comment_authors']==0
    assert decide(evidence)['reason_code']=='REVIEW_CONFLICTING_TEXT_EVIDENCE'


def test_comment_dedupe_across_anonymous_copies_and_captures():
    comments=[{'id':1,'text':'Link please!','author_username':'a'}, {'id':2,'text':'LINK PLEASE','author_username':'a'},
              {'id':3,'text':'Link please','author_username':None},{'id':4,'text':'onde compro','author_username':'b'},
              {'id':5,'text':'eu quero','author_username':'c'},{'id':6,'text':'good product','author_username':'d'},
              {'id':7,'text':'normal conversation','author_username':'e'}]
    result=consumer_signals(comments)
    assert result['sample_size']==5 and result['unique_purchase_intent_comments']==3
    assert result['unique_authors']==3 and result['intent_ratio']==.6
    assert result['strength']=='STRONG' and {1,2,3}<=set(result['evidence_ids'])


def test_identity_independent_quality_and_complaint_evidence():
    comments=[{'id':i,'text':t,'author_username':str(i)} for i,t in enumerate(['link','onde compro','eu quero','price','need','bad quality broken'],1)]
    data=item(comments=comments)
    quality=core.quality(data,{'status':'UNRESOLVED','reason_code':'NO_IDENTITY'})
    assert quality['purchase_intent']['strength']=='STRONG'
    assert quality['product_quality']['status']=='partial'
    assert quality['product_quality']['evidence_ids']==[6]
    assert quality['identity_confidence']['status']=='insufficient_data'
    assert quality['viral_potential']['value'] is None


def test_resource_defer_resumes_without_exhausting_transient_budget(library):
    with library.connect() as con:
        seed(con,None);jid=jobs.enqueue(con,'embedding',1,{})
        for _ in range(5):
            job=jobs.claim(con);jobs.defer(con,job,'RAM pressure')
            assert con.execute('SELECT status FROM intelligence_jobs WHERE id=?',(jid,)).fetchone()[0]=='queued'
            con.execute("UPDATE intelligence_jobs SET available_at='2000-01-01'")
        job=jobs.claim(con);jobs.finish(con,job)
        row=con.execute('SELECT * FROM intelligence_jobs WHERE id=?',(jid,)).fetchone()
        assert row['status']=='completed' and row['resource_wait_count']==5


def test_governor_budget_and_critical_stop(monkeypatch):
    import psutil
    monkeypatch.setattr(psutil,'cpu_percent',lambda interval:20)
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(percent=90,available=1600*1048576))
    assert ResourceGovernor().state()['state']=='RUN'
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(percent=96,available=600*1048576))
    assert ResourceGovernor().state()['state']=='DEFER'
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(percent=99,available=100*1048576))
    assert ResourceGovernor().state()['state']=='STOP'


def test_gpu_requires_runtime_allocation_and_falls_back():
    def fail(*a,**kw):raise RuntimeError('allocation failed')
    fake=SimpleNamespace(version=SimpleNamespace(cuda='available'),cuda=SimpleNamespace(is_available=lambda:True,mem_get_info=lambda:(3*1024**3,4*1024**3),synchronize=lambda:None),empty=fail)
    p=OpenCLIPProvider();assert p._select_device(fake)=='cpu'
    assert 'FAILED' in p.runtime_probe['reason']


def test_model_idle_unloads(monkeypatch):
    from app import intelligence_embeddings as module
    settings=module.settings();settings['resources']['idle_unload_seconds']=.01
    monkeypatch.setattr(module,'settings',lambda:settings)
    p=OpenCLIPProvider();p.model=object();p._schedule_unload()
    deadline=time.monotonic()+1
    while p.model is not None and time.monotonic()<deadline:time.sleep(.01)
    assert p.model is None


def test_bootstrap_reference_kinds_and_candidate_not_entity(tmp_path):
    index=ProductIndex(tmp_path)
    entries=[{'reference_id':'candidate:1','reference_kind':'CANDIDATE_REFERENCE','product_id':None,'kind':'text','name':'Soap dispenser','source':{'candidate_id':1},'vector':[1,0]},
             {'reference_id':'entity:1','reference_kind':'PRODUCT_ENTITY','product_id':'entity:1','vector':[0,1]}]
    metadata=index.rebuild(entries,'test-v',2)
    hit=index.search([1,0],'test-v')[0]
    assert metadata['vectors']==2 and metadata['candidate_references']==1 and metadata['entities']==1
    assert hit['reference_kind']=='CANDIDATE_REFERENCE' and hit['product_id'] is None


def test_core_candidate_hit_cannot_create_entity(library,monkeypatch,tmp_path):
    from app.intelligence_embeddings import provider
    with library.connect() as con:
        seed(con,'Generic caption')
        reference={'reference_id':'candidate:1','reference_kind':'CANDIDATE_REFERENCE','product_id':None,'name':'Soap dispenser','source':{},'similarity':1.,'embedding_version':'test','index_version':'generation','observed_at':jobs.now()}
        monkeypatch.setattr(OpenCLIPProvider,'version',property(lambda _:'test'))
        monkeypatch.setattr(provider,'embed',lambda *a:[1,0])
        monkeypatch.setattr(ProductIndex,'metadata',lambda _:None)
        monkeypatch.setattr(ProductIndex,'search',lambda *a:[reference])
        core.identify(con,1,with_embeddings=True)
        assert con.execute('SELECT count(*) FROM intelligence_entities').fetchone()[0]==0
        assert con.execute('SELECT reference_kind FROM intelligence_retrievals').fetchone()[0]=='CANDIDATE_REFERENCE'


def test_production_signals_never_read_gold_or_mutate_security(library):
    with library.connect() as con:
        seed(con,'Soap dispenser and dish brush in one')
        con.execute("INSERT INTO system_state VALUES ('browser_security_stop','{\"reason\":\"HTTP 403\"}','unchanged')")
        before=tuple(con.execute("SELECT * FROM system_state WHERE key='browser_security_stop'").fetchone())
        def guard(action,a,b,db,trigger):return sqlite3.SQLITE_DENY if a and a.startswith('gold_') else sqlite3.SQLITE_OK
        con.set_authorizer(guard)
        core.identify(con,1)
        assert before==tuple(con.execute("SELECT * FROM system_state WHERE key='browser_security_stop'").fetchone())
        con.set_authorizer(lambda *a:sqlite3.SQLITE_OK)
