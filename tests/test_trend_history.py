import json
import sqlite3
import socket
from datetime import datetime,timedelta,timezone
import pytest
from app import trend_history as trend
from test_product_detection import library,seed


@pytest.fixture
def con():
    c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE videos(id INTEGER PRIMARY KEY)');c.execute('INSERT INTO videos VALUES(1)');trend.migrate(c)
    yield c
    c.close()


def put(c,index,metric=100,at=None,**metrics):
    return trend.record_trend_snapshot(c,target_type='VIDEO',target_id=1,video_id=1,
        observed_at=at or f'2026-01-01T0{index}:00:00Z',source='test_counter',source_key=f'fixture:{index}',
        metrics={'views':metric,**metrics},coverage={'creator':'one','basis':'test observations'})


def test_idempotence_null_and_same_timestamp_alias(con):
    sid=put(con,1)
    assert put(con,1)==sid
    trend.record_trend_snapshot(con,target_type='VIDEO',target_id=1,video_id=1,observed_at='2026-01-01T02:00:00+01:00',source='test_counter',source_key='alias',metrics={'views':100},coverage={})
    assert len(trend.snapshots(con,'VIDEO',1))==1
    assert trend.snapshots(con,'VIDEO',1)[0]['metrics']['comments'] is None
    assert con.execute('SELECT count(*) FROM trend_snapshot_sources').fetchone()[0]==2


def test_velocity_two_points_and_explanation(con):
    put(con,1,100);put(con,3,300)
    s=trend.for_video(con,1);v=s['velocity']['views']
    assert v['latest']['value']==100 and v['latest']['unit']=='per_hour'
    assert (v['latest']['from_value'],v['latest']['to_value'],v['latest']['duration_seconds'])==(100,300,7200)
    assert v['acceleration']['status']=='INSUFFICIENT_HISTORY'
    assert s['lifecycle']=='EARLY_SIGNAL' and s['quality']['strength']=='LOW'


@pytest.mark.parametrize('last,state',[(400,'ACCELERATING'),(300,'STABLE'),(250,'DECELERATING')])
def test_acceleration_uses_actual_intervals(con,last,state):
    put(con,1,100);put(con,2,200);put(con,3,last)
    a=trend.for_video(con,1)['velocity']['views']['acceleration']
    assert a['status']==state


def test_zero_is_observed_not_missing_and_no_fake_baseline(con):
    put(con,1,0)
    assert trend.for_video(con,1)['velocity']['views']['status']=='INSUFFICIENT_HISTORY'
    put(con,2,0)
    assert trend.for_video(con,1)['velocity']['views']['latest']['value']==0
    assert trend.for_video(con,1)['velocity']['likes']['latest'] is None


def test_conflicting_same_time_not_arbitrarily_selected(con):
    put(con,1,100);put(con,2,200,at='2026-01-01T01:00:00Z')
    s=trend.for_video(con,1)
    assert s['conflicting_timestamps']['views']
    assert s['velocity']['views']['latest'] is None


def test_creator_and_purchase_sample_momentum(con):
    put(con,1,None,at='2026-01-01T00:00:00Z',unique_creators_known=3,purchase_intent_unique_authors=12)
    put(con,2,None,at='2026-01-03T00:00:00Z',unique_creators_known=8,purchase_intent_unique_authors=31)
    s=trend.for_video(con,1)
    assert s['creator_momentum']['new_unique_creators']==5
    assert s['creator_momentum']['creator_arrival_rate']['value']==2.5
    assert s['purchase_intent_momentum']['latest']['value']==9.5
    assert s['creator_momentum']['independence']=='NOT_ESTABLISHED'


def test_sample_collection_alone_is_not_product_growth(con):
    put(con,1,None,purchase_intent_unique_authors=2);put(con,2,None,purchase_intent_unique_authors=20)
    s=trend.for_video(con,1)
    assert s['purchase_intent_momentum']['status']=='measured'
    assert s['momentum']=='INSUFFICIENT_HISTORY'


def test_change_point_short_series_does_not_import_heavy_adapter():
    assert trend.change_points([])=={'status':'INSUFFICIENT_HISTORY','evidence':[]}


def test_incremental_dedup_and_checkpoint(con):
    class Model:
        def __init__(self):self.calls=[]
        def learn_one(self,x):self.calls.append(x)
    put(con,1);r=trend.snapshots(con,'VIDEO',1)[0];m=Model();a=trend.IncrementalAdapter(m)
    assert a.consume(r) and not a.consume(r)
    b=trend.IncrementalAdapter(m,a.checkpoint()['seen_snapshot_ids']);assert not b.consume(r)
    assert len(m.calls)==1 and 'comments' not in m.calls[0]


@pytest.mark.parametrize('value',[-1,float('inf'),float('nan'),True,'Curtida'])
def test_reject_invalid_metrics(con,value):
    with pytest.raises(ValueError):put(con,1,value)


def test_source_correction_requires_version(con):
    put(con,1,100)
    with pytest.raises(ValueError):put(con,1,200)


def test_category_and_lifecycle_conservative(con):
    put(con,1,10);put(con,2,100);put(con,3,1000)
    s=trend.summarize(trend.snapshots(con,'VIDEO',1),'CATEGORY')
    assert s['momentum']=='INSUFFICIENT_HISTORY'
    assert s['lifecycle']=='DISCOVERED'
    assert s['quality']['strength']=='LOW'


def test_bootstrap_does_not_use_first_seen_or_mutate_gold_security(library,monkeypatch):
    monkeypatch.setattr(socket,'socket',lambda *a,**k: (_ for _ in ()).throw(AssertionError('network forbidden')))
    with library.connect() as c:
        vid=seed(c,'Mini mop')
        c.execute("INSERT INTO system_state(key,value_json,updated_at) VALUES('browser_security_stop','{\"reason\":\"HTTP 403\"}','2026-01-01')")
        before=[tuple(r) for r in c.execute('SELECT * FROM system_state')]
        assert trend.import_history(c)==0
        assert trend.snapshots(c,'VIDEO',vid)==[]
        assert before==[tuple(r) for r in c.execute('SELECT * FROM system_state')]
        assert c.execute('SELECT count(*) FROM videos').fetchone()[0]==1


def test_bootstrap_normalizes_persisted_numeric_strings_only(library):
    with library.connect() as c:
        vid=seed(c,'Mini mop')
        for index,fields in enumerate([{'likes':'31.2K','comments_count':'119','shares':'Compartilhar'}, {'likes':'31.3K','comments_count':'120','favorites':'Favoritos'}],1):
            c.execute('INSERT INTO video_detail_observations(video_id,command_id,observed_at,extractor_version,fields_json,field_evidence_json) VALUES (?,?,?,?,?,?)',
                (vid,index,f'2026-01-01T0{index}:00:00Z','fixture',json.dumps(fields),'{}'))
        trend.import_history(c)
        s=trend.for_video(c,vid)
        assert s['velocity']['likes']['latest']['value']==100
        assert s['velocity']['comments']['latest']['value']==1
        assert s['velocity']['favorites']['latest'] is None
        assert trend.import_history(c)==0


def test_quality_is_independent_of_zero_magnitude(con):
    for i in range(3):
        trend.record_trend_snapshot(con,target_type='CANDIDATE',target_id='x',observed_at=f'2026-01-0{i+1}T00:00:00Z',source='cohort',source_key=f'quality:{i}',
            metrics={'views':100,'known_video_count':3,'unique_creators_known':3},coverage={'creator_coverage':1})
    s=trend.summarize(trend.snapshots(con,'CANDIDATE','x'),'CANDIDATE')
    assert s['quality']['strength']=='HIGH'
    assert s['momentum']=='STABLE' and s['velocity']['views']['latest']['value']==0


def test_coverage_correction_not_silently_ignored(con):
    put(con,1)
    with pytest.raises(ValueError,match='coverage changed'):
        trend.record_trend_snapshot(con,target_type='VIDEO',target_id=1,observed_at='2026-01-01T01:00:00Z',source='test_counter',source_key='fixture:1',metrics={'views':100},coverage={'creator':'different'})


def test_entity_membership_not_backdated_before_human_confirmation(library):
    with library.connect() as c:
        vid=seed(c,'Mini mop')
        decision=c.execute("INSERT INTO intelligence_decisions(video_id,input_hash,policy_version,status,reason_code,name,result_json,evidence_json,created_at) VALUES (?,?,?,'REVIEW','TEST','Mop','{}','{}',?)",(vid,'fixture','fixture','2026-01-01T00:00:00Z')).lastrowid
        c.execute("INSERT INTO intelligence_entities VALUES ('p','Mop',?,'human_confirmed','2026-01-01T00:00:00Z')",(decision,))
        c.execute("INSERT INTO intelligence_entity_observations VALUES (?,'p',?)",(decision,vid))
        c.execute("INSERT INTO intelligence_reviews(decision_id,action,name,product_id,notes,observed_at) VALUES (?,'confirm','Mop','p','','2026-01-03T00:00:00Z')",(decision,))
        for day in (1,4):
            trend.record_trend_snapshot(c,target_type='VIDEO',target_id=vid,video_id=vid,observed_at=f'2026-01-0{day}T00:00:00Z',source='fixture',source_key=f'entity:{day}',metrics={'views':day*100},coverage={'creator':'a'})
        trend.build_aggregates(c)
        rows=trend.snapshots(c,'PRODUCT_ENTITY','p')
        assert rows[0]['observed_at'].startswith('2026-01-03') and rows[0]['metrics']['views'] is None
        assert rows[1]['metrics']['views']==400
