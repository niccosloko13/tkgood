from scripts.process_runtime import hidden_kwargs
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import subprocess

import pytest
from pydantic import ValidationError
from app import db
from app.creator_schemas import CreatorProfile,CreatorCommand,profile_identity,normalize_count
from app.creators import bucket,performance,profile_signals,records,creator_for_video
from app.policy import ReadOnlyPolicy
from test_capture import api,database,capture_body


def profile():
    return json.loads(subprocess.check_output(['node','tests/creator_payload.cjs'],text=True,timeout=10, **hidden_kwargs()))


def seed(call):
    call('/api/bridge/heartbeat',{'current_url':'https://www.tiktok.com/search?q=home+gadgets'})
    body=capture_body();body['results'][0].update(creator_username='@Maker',video_id='123',search_position=1,
        extraction_version='tiktok-search-card-v2',extraction_completeness=.5,
        field_evidence={key:{'value':value,'confidence':confidence,'source':'search_card'} for key,value,confidence in
            [('creator_username','@Maker',.98),('video_url','https://www.tiktok.com/@maker/video/123',1.),('video_id','123',1.)]})
    command=call('/api/commands',{'type':'READ_SEARCH_RESULTS'})[1]['id']
    call('/api/bridge/commands/next?extension_id=ext')
    assert call(f'/api/bridge/commands/{command}/result',{'extension_id':'ext','status':'SUCCEEDED','capture':body})[0]==200


def read(call,payload):
    command=call('/api/commands',{'type':'READ_CREATOR_PROFILE','video_url':'https://www.tiktok.com/@maker/video/123'})[1]['id']
    claimed=call('/api/bridge/commands/next?extension_id=ext')[1]['command']
    assert claimed['query']=='https://www.tiktok.com/@maker'
    assert json.loads(claimed['options_json'])['video_url']=='https://www.tiktok.com/@maker/video/123'
    route=f'/api/bridge/commands/{command}/result'
    body={'extension_id':'ext','status':'SUCCEEDED','creator_profile':payload}
    assert call(route,body)[0]==200
    return route,body


def test_creator_contract_normalization_and_missing_values():
    assert profile_identity('https://tiktok.com/@MaKer/?lang=en#x')==('https://www.tiktok.com/@maker','@maker')
    for raw,expected in [('31.2K',31200),('31,2K',31200),('1.4M',1400000),('2B',2000000000),('0',0),('1,234',None),('1.234',None),('label',None),('1.2',None)]:
        assert normalize_count(raw)==expected
    payload=profile();CreatorProfile(**payload)
    for changes in ({'followers':1},{'username':'@another'},{'type':'FOLLOW'},{'external_link':'javascript:bad'},{'following':'123'}):
        with pytest.raises(ValidationError):CreatorProfile(**{**payload,**changes})
    for field in ('bio','external_link','display_name'):
        payload[field]=None;payload['field_evidence'].pop(field)
    payload['links']=[]
    assert CreatorProfile(**payload).bio is None
    assert ReadOnlyPolicy().check('READ_CREATOR_PROFILE').allowed
    for action in ('LIKE','FOLLOW','UNFOLLOW','DM','REPLY','COMMENT','SHARE','SAVE'):
        assert not ReadOnlyPolicy().check(action).allowed
    with pytest.raises(ValidationError):CreatorCommand(type='READ_CREATOR_PROFILE',video_url='https://www.tiktok.com/@maker')


def test_buckets_ratios_and_explainable_score():
    assert [bucket(n) for n in (None,0,9999,10000,49999,50000,249999,250000,999999,1000000,2000000)]==[None,'micro','micro','small','small','medium','medium','large','large','mega','mega']
    evidence={key:{'value':value,'confidence':.98} for key,value in [('views',600000),('likes',12000),('comments_count',900),('shares',1800)]}
    result=performance(evidence,18000)
    assert result['views_to_followers_ratio']==33.333333
    assert result['comments_to_followers_ratio']==.05
    assert result['shares_to_followers_ratio']==.1
    assert result['creator_independence_score']==98
    assert result['creator_independence_score']==sum(result['score_components'].values())
    assert performance(evidence,0)['creator_independence_score'] is None
    assert performance({},18000)['views_to_followers_ratio'] is None
    assert performance({},18000)['creator_independence_score'] is None
    assert performance({'views':{'value':0,'confidence':.98},'likes':{'value':0,'confidence':.98}},9000)['creator_independence_score']==10
    assert performance({'views':{'value':2251,'confidence':0},'likes':{'value':2251,'confidence':.98}},1187)['creator_independence_score'] is None
    signals=profile_signals({'followers':18000,'total_likes':36000,'video_count':20},[{'url':'https://shop.example/?affiliate=maker','label':'shop'}])
    assert signals['followers_to_video_ratio']==900 and signals['likes_per_follower_ratio']==2
    assert signals['has_external_link'] and signals['has_commercial_link'] and signals['has_shop_signal']


def test_http_profile_payload_dedup_history_provenance_and_preservation(api):
    _,call=api;seed(call)
    videos=call('/api/videos/recent')[1];quality=call('/api/extraction/quality')[1]
    payload=profile();route,body=read(call,payload)
    assert call(route,body)[0]==200
    changed=copy.deepcopy(body);changed['creator_profile']['bio']='Changed';changed['creator_profile']['field_evidence']['bio']['value']='Changed'
    assert call(route,changed)[0]==409
    first=call('/api/creators')[1]['items'][0]
    assert first['username']=='@maker' and first['followers']==31200
    assert first['observation_count']==1 and first['signals']['creator_size_bucket']=='small'
    assert first['related_videos'][0]['video_url']==videos['items'][0]['video_url']
    assert first['related_videos'][0]['creator_profile_url']==first['profile_url']
    evidence=first['latest_observation']['field_evidence']['followers']
    assert evidence['source']=='creator_profile' and evidence['raw_value']=='31.2K' and evidence['normalized_value']==31200
    assert evidence['observed_at']==first['latest_observed_at']
    read(call,payload)
    latest=call('/api/creators/'+str(first['creator_id']))[1]['items'][0]
    assert latest['observation_count']==2 and latest['creator_id']==first['creator_id']
    assert latest['first_seen_at']==first['first_seen_at']
    with db.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM creators').fetchone()[0]==1
        assert con.execute('SELECT COUNT(*) FROM creator_profile_observations').fetchone()[0]==2
        assert con.execute('SELECT COUNT(*) FROM video_creators').fetchone()[0]==1
    assert call('/api/videos/recent')[1]==videos and call('/api/extraction/quality')[1]==quality
    assert call('/api/creators/9999')[0]==404


def test_profile_gates_wrong_identity_and_command_type(api):
    _,call=api
    assert call('/api/commands',{'type':'READ_CREATOR_PROFILE','video_url':'https://www.tiktok.com/@maker/video/123'})[0]==409
    seed(call)
    assert call('/api/commands',{'type':'READ_CREATOR_PROFILE','video_url':'https://www.tiktok.com/@maker/video/999'})[0]==404
    command=call('/api/commands',{'type':'READ_CREATOR_PROFILE','video_url':'https://www.tiktok.com/@maker/video/123'})[1]['id']
    assert call('/api/commands',{'type':'READ_CREATOR_PROFILE','video_url':'https://www.tiktok.com/@maker/video/123'})[0]==409
    call('/api/bridge/commands/next?extension_id=ext')
    wrong=profile();wrong['username']='@other';wrong['profile_url']='https://www.tiktok.com/@other'
    for key in ('username','profile_url'):wrong['field_evidence'][key]['value']=wrong[key]
    assert call(f'/api/bridge/commands/{command}/result',{'extension_id':'ext','status':'SUCCEEDED','creator_profile':wrong})[0]==409
    assert call(f'/api/bridge/commands/{command}/result',{'extension_id':'ext','status':'SUCCEEDED'})[0]==409
    assert call('/api/creators')[1]['items'][0]['latest_observation'] is None


def test_new_missing_or_ambiguous_count_keeps_history_but_does_not_reuse_old_denominator(api):
    _,call=api;seed(call);payload=profile();read(call,payload)
    original=call('/api/creators')[1]['items'][0]
    payload['followers']=None
    payload['field_evidence']['followers'].update(value=None,normalized_value=None,raw_value='1,234')
    read(call,payload)
    current=call('/api/creators')[1]['items'][0]
    assert current['creator_id']==original['creator_id'] and current['observation_count']==2
    assert current['followers'] is None  # latest projection, not a stale denominator
    assert current['latest_observation']['followers'] is None
    assert current['latest_observation']['field_evidence']['followers']['raw_value']=='1,234'
    assert current['signals']['follower_count'] is None
    assert current['related_videos'][0]['views_to_followers_ratio'] is None
    with db.connect() as con:
        assert con.execute('SELECT followers FROM creator_profile_observations ORDER BY id LIMIT 1').fetchone()[0]==31200


def test_migration_preserves_existing_command_options_and_profile_dedup(database):
    now=datetime.now(timezone.utc).isoformat()
    with db.connect() as con:
        con.execute('DROP TABLE bridge_commands')
        con.execute("""CREATE TABLE bridge_commands(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT,updated_at TEXT,
            type TEXT CHECK(type IN ('SEARCH','READ_COMMENTS_SAMPLE')),query TEXT,status TEXT,extension_id TEXT,detail TEXT,
            result_hash TEXT,options_json TEXT)""")
        con.execute("INSERT INTO bridge_commands VALUES (7,?,?,'READ_COMMENTS_SAMPLE','url','SUCCEEDED','ext','detail','hash','{\"target_count\":30}')",(now,now))
    db.init_db();db.init_db()
    with db.connect() as con:
        row=dict(con.execute('SELECT * FROM bridge_commands WHERE id=7').fetchone())
        assert row['result_hash']=='hash' and json.loads(row['options_json'])['target_count']==30
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not con.execute('PRAGMA foreign_key_check').fetchall()
