import copy
import json
import socket
import sqlite3
from pathlib import Path
import pytest
from app.comments import consumer_signals_v2
from app.intelligence_signals import analyze, persist


def comment(text, author='a', id=1, **kw):
    return dict(text=text,author_username=author,id=id,**kw)


@pytest.mark.parametrize('text,kind',[
    ('onde compro?','WHERE_TO_BUY'),('where can I buy?','WHERE_TO_BUY'),('donde lo compro','WHERE_TO_BUY'),
    ('link please','LINK_REQUEST'),('qual pre\u00e7o','PRICE_QUESTION'),('price?','PRICE_QUESTION'),
    ('eu quero','WANT'),('quiero','WANT'),('I need','NEED'),('preciso','NEED'),
    ('comprei','PURCHASE_DECLARATION'),('is it available?','AVAILABILITY_QUESTION')])
def test_multilingual_intent(text,kind):
    assert consumer_signals_v2([comment(text)])['intent_types'][kind]['comments']==1


def test_author_dedupe_and_coverage():
    p=consumer_signals_v2([comment('link',id=1),comment('LINK',id=2),comment('link','b',3),comment('link',None,4),comment('I need','a',5)])
    assert p['sample_size']==3 and p['unique_intent_authors']==2 and p['intent_comments']==3
    assert p['strength']=='MODERATE' and p['status']=='partial'
    assert set(p['evidence_ids'])=={1,2,3,5}


def test_partial_platform_ids_do_not_double_count():
    p=consumer_signals_v2([comment('link',comment_id='123'),comment('LINK',id=2),comment('link',id=3,comment_id='456')])
    assert p['sample_size']==1 and p['unique_intent_authors']==1


@pytest.mark.parametrize('text,kind',[('does not work','DOES_NOT_WORK'),("doesn't work",'DOES_NOT_WORK'),('nao funciona','DOES_NOT_WORK'),('no funciona','DOES_NOT_WORK'),('quebrou','BROKE'),('fake','FAKE'),('easy to use','EASY_TO_USE'),('dificil de usar','HARD_TO_USE')])
def test_quality_comment_types(text,kind):
    assert consumer_signals_v2([comment(text)])['consumer_types'][kind]['comments']==1


def test_negation_and_no_fake_demand():
    p=consumer_signals_v2([comment('I do not want it'),comment('nao preciso','b',2),comment('not useful','c',3)])
    assert p['intent_comments']==0
    assert p['consumer_types']['USEFUL']['comments']==0


def test_identity_independent_and_single_creator_limits():
    item=dict(video_id=1,caption='Soap dispenser and dish brush in one',creator='one',comments=[comment('link',str(i),i) for i in range(20)])
    out=analyze(item);d=out['dimensions']
    assert d['purchase_intent']['classification']=='STRONG'
    assert d['signal_quality']['creator_diversity'] is None
    assert d['signal_quality']['status']=='partial'
    assert d['commercial_readiness']['classification']=='PARTIAL'
    assert d['trend_readiness']['classification']=='INSUFFICIENT_HISTORY'
    assert d['creative_dna']['fields']['product_visible_early']['value'] is None
    assert d['viral_potential']['features']['novelty']['status']=='insufficient'
    assert set(d)=={'purchase_intent','signal_quality','viral_potential','creative_dna','product_quality','saturation','trend_readiness','commercial_readiness'}
    assert not any(k in json.dumps(out).lower() for k in ('opportunity_score','winner_score','gold_score'))


def test_no_quality_verdict_from_one_positive_sample():
    d=analyze(dict(comments=[comment('very useful')]))['dimensions']['product_quality']
    assert d['classification']=='INSUFFICIENT_DATA' and d['status']=='partial'


def test_commercial_ready_without_supplier_circular_dependency():
    item=dict(creator='a',confirmed_video_count=2,confirmed_creator_count=2,comments=[comment('I need this useful product',str(i),i) for i in range(30)])
    d=analyze(item,'AUTO')['dimensions']
    assert d['product_quality']['classification']=='PROMISING'
    assert d['commercial_readiness']['classification']=='READY_FOR_SUPPLIER_DISCOVERY'
    assert not d['commercial_readiness']['supplier_data_available']


def test_visual_still_does_not_invent_creative_timing():
    item=dict(proposals=[dict(id=1,provider_payload_json={'data':{'quality':{'product_visibility':{'status':'observed','reason':'visible'}}}})])
    d=analyze(item)['dimensions']
    assert d['viral_potential']['features']['product_visibility']['status']=='observed'
    assert d['creative_dna']['fields']['transformation_present']['status']=='insufficient'
    assert d['creative_dna']['repeatability']['classification']=='INSUFFICIENT'


def test_pure_offline_no_input_mutation_or_gold_use(monkeypatch):
    def denied(*a,**kw):raise AssertionError('network forbidden')
    monkeypatch.setattr(socket,'socket',denied)
    source=dict(caption='Clean windows',comments=[comment('link')],gold_label='not an input')
    before=copy.deepcopy(source);a=analyze(source);source['gold_label']='different'
    assert analyze(source)==a
    source['gold_label']=before['gold_label'];assert source==before


def test_snapshot_idempotent_and_no_business_mutation():
    con=sqlite3.connect(':memory:');con.execute('CREATE TABLE videos(id INTEGER PRIMARY KEY)');con.execute('INSERT INTO videos VALUES(1)')
    result=analyze({});persist(con,1,result);persist(con,1,result)
    assert con.execute('SELECT count(*) FROM intelligence_dimension_snapshots').fetchone()[0]==1
    assert con.execute('SELECT * FROM videos').fetchall()==[(1,)]


def test_all_dimensions_explain_missing_data():
    for dim in analyze({})['dimensions'].values():
        assert all(k in dim for k in ('coverage','sample_size','unique_sources','confidence_status','reason_codes','evidence_ids'))
        assert dim['reason_codes']
    assert analyze({})['dimensions']['purchase_intent']['intent_ratio'] is None


def test_trend_requires_numeric_history_not_repeated_capture():
    item={'observation_times':['2026-01-01','2026-01-02','2026-01-03']}
    assert analyze(item)['dimensions']['trend_readiness']['classification']=='INSUFFICIENT_HISTORY'
    item['engagement_observations']=[{'id':i,'observed_at':f'2026-01-0{i}T00:00:00Z','metrics':{'views':i*100}} for i in (1,2,3)]
    d=analyze(item)['dimensions']['trend_readiness']
    assert d['classification']=='READY_FOR_TREND_ANALYSIS'
    assert d['engagement_velocity'] is None


def test_repeatability_needs_explicit_evidence_not_adjectives():
    item={'caption':'wow new incredible product','creative_observations':{k:dict(status='observed',evidence_ids=['frame:1'],reason_codes=['TEST']) for k in ('multiple_use_cases','multiple_problem_angles','multiple_demo_angles')}}
    d=analyze(item)['dimensions']
    assert d['creative_dna']['repeatability']['classification']=='HIGH'
    assert d['viral_potential']['features']['wow_factor']['status']=='insufficient'
