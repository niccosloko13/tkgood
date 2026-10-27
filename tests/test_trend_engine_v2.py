import json
import sqlite3
from datetime import datetime, timezone

import pytest

from app import trend_engine_v2 as engine


@pytest.fixture
def con():
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.executescript('''
      CREATE TABLE product_candidates(id INTEGER PRIMARY KEY,canonical_name TEXT,first_seen_at TEXT);
      CREATE TABLE product_candidate_evidence(id INTEGER PRIMARY KEY,candidate_id INTEGER,video_id INTEGER,observed_at TEXT);
      CREATE TABLE videos(id INTEGER PRIMARY KEY,creator_username TEXT);
      CREATE TABLE search_observations(id INTEGER PRIMARY KEY,video_id INTEGER,capture_id TEXT,search_query TEXT,observed_at TEXT,fields_json TEXT);
      CREATE TABLE trend_snapshots(id INTEGER PRIMARY KEY,target_type TEXT,target_id TEXT,observed_at TEXT,payload_json TEXT);
    ''')
    engine.migrate(c)
    yield c
    c.close()


def seed(c, rows, candidate_id=1, name='Window cleaner', creator='one'):
    c.execute('INSERT INTO product_candidates VALUES(?,?,?)',(candidate_id,name,'2026-01-01T00:00:00+00:00'))
    c.execute('INSERT INTO videos VALUES(?,?)',(candidate_id,creator))
    for n,(at,query,views,who) in enumerate(rows,1):
        ident=candidate_id*100+n
        c.execute('INSERT INTO product_candidate_evidence VALUES(?,?,?,?)',(ident,candidate_id,candidate_id,at))
        c.execute('INSERT INTO search_observations VALUES(?,?,?,?,?,?)',(ident,candidate_id,f'capture:{candidate_id}:{n}',query,at,json.dumps({'creator_username':who,'views':views})))
        c.execute('INSERT INTO trend_snapshots VALUES(?,?,?,?,?)',(ident,'CANDIDATE',str(candidate_id),at,json.dumps({'views':views})))


def state(c, candidate_id=1, at='2026-01-04T00:00:00+00:00'):
    return engine.candidate_state(c,candidate_id,at)


def test_single_observation_is_discovered_and_insufficient(con):
    seed(con,[('2026-01-01T00:00:00+00:00','home gadgets',100,'one')])
    s=state(con)
    assert s['lifecycle']=='DISCOVERED' and s['evidence_quality']=='INSUFFICIENT'
    assert s['velocity']['views']['status']=='INSUFFICIENT'


def test_recurrence_dedupes_capture_and_spreads_query_and_creator(con):
    seed(con,[('2026-01-01T00:00:00+00:00','home gadgets',100,'one'),('2026-01-01T01:00:00+00:00','home finds',200,'two'),('2026-01-01T02:00:00+00:00','home finds',300,'two')])
    s=state(con)
    assert s['recurrence']['capture_count']==3
    assert s['query_spread']==2 and s['creator_spread']==2
    assert s['same_creator_recurrence']==2 and s['different_creator_spread']==2


def test_velocity_acceleration_and_negative_delta_are_explicit(con):
    seed(con,[('2026-01-01T00:00:00+00:00','home gadgets',100,'one'),('2026-01-01T01:00:00+00:00','home finds',300,'two'),('2026-01-01T02:00:00+00:00','kitchen gadgets',700,'three')])
    s=state(con)
    assert s['velocity']['views']['status']=='RISING'
    assert s['velocity']['views']['acceleration']['status']=='RISING'
    assert s['acceleration_summary']=='RISING'
    con.execute("UPDATE trend_snapshots SET payload_json=? WHERE id=103",(json.dumps({'views':50}),))
    assert state(con)['velocity']['views']['negative_delta']


def test_missing_metrics_and_invalid_time_do_not_become_velocity(con):
    seed(con,[('2026-01-01T00:00:00+00:00','home gadgets',None,'one'),('2026-01-01T01:00:00+00:00','home finds',None,'two')])
    assert state(con)['velocity']['views']['status']=='INSUFFICIENT'
    con.execute("INSERT INTO search_observations VALUES(99,1,'capture:bad','other','bad-time','{}')")
    assert state(con)['observation_count']==2


@pytest.mark.parametrize('inputs,expected',[
    ((1,'INSUFFICIENT','INSUFFICIENT',1,1,'INSUFFICIENT','INSUFFICIENT','INSUFFICIENT'),'DISCOVERED'),
    ((2,'LOW','LOW',1,1,'STABLE','INSUFFICIENT','LOW'),'EARLY_SIGNAL'),
    ((3,'MEDIUM','MEDIUM',2,1,'RISING','INSUFFICIENT','LOW'),'EMERGING'),
    ((6,'HIGH','HIGH',3,2,'RISING','RISING','LOW'),'ACCELERATING'),
    ((8,'HIGH','HIGH',4,3,'RISING','RISING','LOW'),'BREAKOUT'),
    ((8,'HIGH','HIGH',5,4,'RISING','STABLE','MEDIUM'),'MAINSTREAM'),
    ((6,'MEDIUM','MEDIUM',2,1,'STABLE','STABLE','HIGH'),'SATURATED'),
    ((6,'MEDIUM','MEDIUM',2,1,'FALLING','FALLING','LOW'),'DECLINING'),
])
def test_lifecycle_rules_are_documented_and_conservative(inputs,expected):
    assert engine._lifecycle(*inputs)==expected


def test_saturation_requires_multiple_signals(con):
    assert engine._saturation(2,.99,1,1,False)=='INSUFFICIENT'
    assert engine._saturation(8,.9,1,1,False)=='HIGH'
    assert engine._saturation(8,.1,3,3,True)=='LOW'


def test_recompute_is_idempotent_and_records_no_duplicate_change_event(con):
    seed(con,[('2026-01-01T00:00:00+00:00','home gadgets',100,'one'),('2026-01-01T01:00:00+00:00','home finds',200,'two'),('2026-01-01T02:00:00+00:00','kitchen gadgets',300,'three')])
    first=engine.recompute(con,'2026-01-03T00:00:00+00:00')
    second=engine.recompute(con,'2026-01-03T00:00:00+00:00')
    assert first['changed']==1 and second['changed']==0
    assert con.execute('SELECT count(*) FROM top_opportunities').fetchone()[0]==1
    assert con.execute('SELECT count(*) FROM trend_change_events').fetchone()[0]==0


def test_why_and_risks_are_deterministic_and_explain_evidence(con):
    seed(con,[('2026-01-01T00:00:00+00:00','home gadgets',100,'one'),('2026-01-01T01:00:00+00:00','home finds',200,'two'),('2026-01-01T02:00:00+00:00','kitchen gadgets',300,'three')])
    one=state(con);two=state(con)
    assert one['why']==two['why'] and any(x['code']=='QUERY_SPREAD' for x in one['why'])
    assert all('evidence_ids' in x for x in one['why']+one['risks']+one['insufficient_signals'])


def test_prediction_snapshot_is_immutable_and_backtest_has_no_future_leakage(con):
    seed(con,[('2026-01-01T00:00:00+00:00','home gadgets',100,'one'),('2026-01-01T01:00:00+00:00','home finds',200,'two'),('2026-01-01T02:00:00+00:00','kitchen gadgets',400,'three'),('2026-01-01T07:00:00+00:00','cleaning gadgets',800,'four')])
    before=engine.candidate_state(con,1,'2026-01-01T02:00:00+00:00')
    # A checkpoint is intentionally constructed at T0 to exercise the evaluator.
    con.execute('''INSERT INTO prediction_checkpoints(candidate_id,prediction_time,lifecycle,momentum,source_hash,evidence_snapshot_json,metrics_snapshot_json,why_snapshot_json,created_at)
      VALUES(?,?,?,?,?,?,?,?,?)''',(1,'2026-01-01T02:00:00+00:00','EMERGING','HIGH','fixture',json.dumps({'observation_ids':before['observation_ids'],'capture_count':before['recurrence']['capture_count'],'query_spread':before['query_spread'],'creator_spread':before['creator_spread']}),'{}','[]','2026-01-01T02:00:00+00:00'))
    checkpoint=con.execute('SELECT * FROM prediction_checkpoints').fetchone()
    result,evidence=engine._outcome_at(con,checkpoint,6,datetime(2026,1,1,5,tzinfo=timezone.utc))
    assert result=='UNKNOWN' and evidence['reason']=='FUTURE_WINDOW_NOT_AVAILABLE'
    result,_=engine._outcome_at(con,checkpoint,6,datetime(2026,1,1,10,tzinfo=timezone.utc))
    assert result=='GREW'
    assert engine.evaluate_predictions(con,'2026-01-01T05:00:00+00:00')==3
    assert con.execute("SELECT result FROM prediction_evaluations WHERE horizon_hours=6").fetchone()[0]=='UNKNOWN'
    assert engine.evaluate_predictions(con,'2026-01-01T10:00:00+00:00')==1
    assert con.execute("SELECT result FROM prediction_evaluations WHERE horizon_hours=6").fetchone()[0]=='GREW'
    assert con.execute('SELECT count(*) FROM prediction_evaluations').fetchone()[0]==3
    with pytest.raises(sqlite3.IntegrityError): con.execute("UPDATE prediction_checkpoints SET momentum='LOW' WHERE id=?",(checkpoint['id'],))


def test_opportunity_ordering_penalizes_high_saturation_and_separates_watchlist(con):
    seed(con,[('2026-01-01T00:00:00+00:00','home gadgets',100,'one'),('2026-01-01T01:00:00+00:00','home finds',200,'two'),('2026-01-01T02:00:00+00:00','kitchen gadgets',500,'three')])
    seed(con,[('2026-01-01T00:00:00+00:00','home gadgets',100,'solo'),('2026-01-01T01:00:00+00:00','home gadgets',100,'solo'),('2026-01-01T02:00:00+00:00','home gadgets',100,'solo'),('2026-01-01T03:00:00+00:00','home gadgets',100,'solo'),('2026-01-01T04:00:00+00:00','home gadgets',100,'solo')],2,'Repeated card','solo')
    engine.recompute(con,'2026-01-03T00:00:00+00:00')
    items=engine.opportunities(con)
    assert items['top_opportunities'][0]['candidate_id']==1
    assert any(x['candidate_id']==2 for x in items['watchlist'])
