import json
from datetime import datetime,timezone,timedelta
import pytest
from app import category_intelligence as ci
from app import night_discovery as night
from test_product_detection import library,seed

def source(text,kind='caption'):
    return {'type':kind,'text':text,'source_entity':'fixture','source_id':1,'url':'https://example.invalid'}

def test_taxonomy_and_classifier():
    c=ci.config()
    assert c['version']=='category-taxonomy-v1' and len(c['categories'])==14
    assert len(c['categories']['home']['subcategories'])==9
    r=ci.classify([source('floor brush')]);assert r['primary_subcategory']=='cleaning'
    assert r['category_evidence'][0]['matched_term']=='floor brush'
    assert ci.classify([source('wow viral gadgets')])['category_status']=='unclassified'
    assert ci.classify([source('vacuum cleaner and facial massager')])['category_status']=='ambiguous'
    assert ci.classify([source('floor brush','search_query'),source('floor brush','creator_context')])['category_status']=='unclassified'
    assert ci.classify([source('floor brush')]*50)['category_confidence']==r['category_confidence']

def test_additive_classification_filters_review_and_idempotency(library):
    with library.connect() as con:
        seed(con,'floor brush',n=1)
        seed(con,'plain text',username='@second',n=2)
        ci.migrate(con)
        before=[tuple(r) for r in con.execute('SELECT * FROM videos')]
        assert ci.classify_library(con)['classifications_created']==2
        assert ci.classify_library(con)['classifications_created']==0
        assert len(ci.library(con,{'category':'home','subcategory':'cleaning'}))==1
        assert len(ci.library(con,{'has_product':'no'}))==2
        assert len(ci.library(con,{'enrichment':'pending'}))==2
        ci.review_category(con,1,{'primary_category':'beauty','human_reviewed':True})
        assert ci.library(con,{'category':'beauty'})[0]['category']['human_review']
        assert con.execute('SELECT count(*) FROM video_category_classifications').fetchone()[0]==2
        assert [tuple(r) for r in con.execute('SELECT * FROM videos')]==before
        with pytest.raises(ValueError):ci.review_category(con,1,{'primary_category':'beauty','primary_subcategory':'cleaning','human_reviewed':True})
        with pytest.raises(ValueError):ci.review_category(con,1,{'primary_category':'home'})

def test_query_metrics_unknown_rates_and_planner(library):
    with library.connect() as con:
        ci.migrate(con)
        q=ci.query_metrics(con)
        assert len(q)==15 and all(x['novelty_rate'] is None for x in q)
        plan=ci.plan(con);assert plan['selected_query'] and plan['reason']
        assert ci.plan(con,excluded=[q['query'] for q in q])['selected_query'] is None

def test_query_novelty_denominator_and_cooldown(library,monkeypatch):
    inventory=[{'queries':['kitchen gadgets'],'creator':f'@creator{i%11}',
        'candidates':[{}] if i<14 else [],'unresolved':[],
        'category':{'primary_category':'home','primary_subcategory':'kitchen','category_status':'classified'}} for i in range(30)]
    monkeypatch.setattr(ci,'library',lambda con:inventory)
    with library.connect() as con:
        con.execute('''INSERT INTO discovery_sessions(command_id,query,created_at,status,max_scrolls,max_new_videos,max_runtime,
            discovery_version,unique_videos,new_videos,duplicates) VALUES (1,'kitchen gadgets',?,'FINISHED',5,25,90,'test',30,21,44)''',(ci.now(),))
        q=next(q for q in ci.query_metrics(con) if q['query']=='kitchen gadgets')
        assert q['novelty_rate']==.7 and q['duplicate_rate']==.3
        assert q['candidate_rate']==14/30 and q['unique_creators']==11
        assert q['duplicates']==9 and q['raw_duplicate_appearances']==44
        assert ci.plan(con)['selected_query']!='kitchen gadgets'

def test_runner_limits():
    settings=ci.config('discovery_intelligence')['runner']
    assert night.stop_reason(settings,{'sessions':12},1)=='max_sessions'
    assert night.stop_reason(settings,{'new_videos':200},1)=='max_total_new_videos'
    assert night.stop_reason(settings,{},3600)=='max_runtime'
    assert night.stop_reason(settings,{},0) is None

def test_runner_security_stop_never_submits(library,monkeypatch):
    class Blocked:
        def security(self):return 'HTTP 403'
        def submit(self,*args):raise AssertionError('Must never issue commands')
    monkeypatch.setattr(night.db,'connect',library.connect)
    with library.connect() as con:
        ci.migrate(con)
        rid=con.execute("INSERT INTO night_discovery_runs(created_at,updated_at,status,settings_json) VALUES (?,?,'running',?)",
            (ci.now(),ci.now(),json.dumps(ci.config('discovery_intelligence')['runner']))).lastrowid
    night.run(rid,adapter=Blocked())
    with library.connect() as con:
        row=con.execute('SELECT * FROM night_discovery_runs WHERE id=?',(rid,)).fetchone()
        assert row['stop_reason']=='security_stop' and row['status']=='stopped'
        assert con.execute('SELECT count(*) FROM night_discovery_checkpoints').fetchone()[0]==1


def test_runner_resumes_captured_session_without_new_commands_and_checkpoints(library,monkeypatch):
    class Offline:
        def security(self):return None
        def submit(self,*args):raise AssertionError('Captured stage must not navigate')
    monkeypatch.setattr(night.db,'connect',library.connect)
    with library.connect() as con:
        seed(con,'portable blender',n=1)
        ci.migrate(con)
        sid=con.execute('''INSERT INTO discovery_sessions(command_id,query,created_at,status,max_scrolls,max_new_videos,max_runtime,discovery_version,new_videos)
            VALUES (1,'kitchen gadgets',?,'FINISHED',5,25,90,'test',1)''',(ci.now(),)).lastrowid
        con.execute('INSERT INTO discovery_session_videos VALUES (?,?,0,1)',(sid,1))
        settings={**ci.config('discovery_intelligence')['runner'],'max_sessions':1,'cooldown_seconds':0}
        progress={'sessions':0,'new_videos':0,'queries':[],'stage':'PROCESS','active_query':'kitchen gadgets','session_id':sid}
        rid=con.execute("INSERT INTO night_discovery_runs(created_at,updated_at,status,settings_json,checkpoint_json) VALUES (?,?,'running',?,?)",
            (ci.now(),ci.now(),json.dumps(settings),json.dumps(progress))).lastrowid
    night.run(rid,adapter=Offline(),sleep=lambda _:None)
    with library.connect() as con:
        row=con.execute('SELECT * FROM night_discovery_runs WHERE id=?',(rid,)).fetchone()
        assert row['stop_reason']=='max_sessions'
        progress=json.loads(row['checkpoint_json'])
        assert progress['sessions']==1 and progress['new_videos']==1
        assert con.execute('SELECT count(*) FROM product_detection_runs').fetchone()[0]==1
        assert con.execute('SELECT count(*) FROM video_category_classifications').fetchone()[0]>=1
