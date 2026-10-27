import json
from datetime import datetime,timezone,timedelta
import pytest
from fastapi import HTTPException
from app import db,safe_collection as safe,target_safety,category_intelligence as ci
from test_product_detection import library
from test_safe_collection import ready,capture,confirm,EXT,bridge


def stage1_passed():
    with db.connect() as c:ident=ready(c);job=safe.start(c,ident,['home organization'])
    db.claim_command(EXT);assert db.finish_command(job['command_id'],EXT,'SUCCEEDED','one',capture())=='ok'
    return ident


def authorize(ident,queries):
    with db.connect() as c:
        fresh=safe.request_check(c,EXT)['id'];confirm(c,fresh)
        safe.authorize_stage2(c,ident,fresh,queries,EXT)


def test_explicit_casa_pack_authorization_accepts_unseen_query_after_stage1(library):
    ident=stage1_passed();queries=['home finds','useful home products','kitchen gadgets','cleaning gadgets','home gadgets']
    with db.connect() as c:
        with pytest.raises(HTTPException):safe.start(c,ident,queries,2)
    authorize(ident,queries)
    with db.connect() as c:
        with pytest.raises(HTTPException):safe.start(c,ident,['unexpected'],2)
        job=safe.start(c,ident,queries,2)
        options=json.loads(c.execute('SELECT options_json FROM bridge_commands WHERE id=?',(job['command_id'],)).fetchone()[0])
        assert options['max_results']==10 and options['max_scrolls']==0 and options['deadline_at']
        with pytest.raises(HTTPException):safe.start(c,ident,queries,2)


def test_query_metrics_snapshots_dedupe_quarantine_and_no_enrichment(library):
    ident=stage1_passed();authorize(ident,['home finds'])
    with db.connect() as c:
        target_safety.quarantine(c,'https://www.tiktok.com/@maker/video/123',safe.now())
        jobs_before=c.execute('SELECT count(*) FROM intelligence_jobs').fetchone()[0]
        job=safe.start(c,ident,['home finds'],2)
    db.claim_command(EXT)
    payload=capture('home finds');payload['page_url']='https://www.tiktok.com/search?q=home+finds'
    base={**payload['results'][0],'caption':'portable blender'}
    payload.update(results=[base,{**base,'video_url':'https://www.tiktok.com/@other/video/124','video_id':'124','creator_username':'@other'}],results_count=2,links_detected=2,invalid_results=1)
    assert db.finish_command(job['command_id'],EXT,'SUCCEEDED','search only',payload)=='ok'
    assert db.finish_command(job['command_id'],EXT,'SUCCEEDED','search only',payload)=='ok'
    with db.connect() as c:
        m=dict(c.execute('SELECT * FROM safe_query_metrics').fetchone())
        assert (m['results'],m['new_videos'],m['duplicates'],m['blocked'],m['invalid'],m['unique_creators'],m['snapshots'])==(2,1,1,1,1,2,2)
        assert datetime.fromisoformat(m['observed_at']).tzinfo
        assert c.execute('SELECT count(*) FROM intelligence_jobs').fetchone()[0]==jobs_before
        assert c.execute('SELECT count(*) FROM videos').fetchone()[0]==2
        assert c.execute('SELECT count(*) FROM search_observations WHERE capture_id=?',(f"command:{job['command_id']}",)).fetchone()[0]==2
        metrics=next(q for q in ci.query_metrics(c) if q['query']=='home finds')
        assert (metrics['videos_seen'],metrics['new_videos'],metrics['duplicates'],metrics['runs'])==(2,1,1,1)
        assert metrics['last_run']==m['observed_at']


def test_authorization_rejects_nonpack_queries_and_missing_pass(library):
    with db.connect() as c:
        ident=ready(c);fresh=safe.request_check(c,EXT)['id'];confirm(c,fresh)
        with pytest.raises(HTTPException):safe.authorize_stage2(c,ident,fresh,['home finds'],EXT)
    ident=stage1_passed()
    with db.connect() as c:
        fresh=safe.request_check(c,EXT)['id'];confirm(c,fresh)
        with pytest.raises(HTTPException):safe.authorize_stage2(c,ident,fresh,['external arbitrary query'],EXT)


def test_stage2_reserves_runtime_and_refuses_unsafe_next_query(library):
    ident=stage1_passed();authorize(ident,['home finds','kitchen gadgets'])
    with db.connect() as c:job=safe.start(c,ident,['home finds','kitchen gadgets'],2)
    db.claim_command(EXT);payload=capture('home finds');payload['page_url']='https://www.tiktok.com/search?q=home+finds'
    db.finish_command(job['command_id'],EXT,'SUCCEEDED','one',payload)
    with db.connect() as c:
        safe.put(c,'tiktok_bridge',{**bridge(),'tiktok_session_status':'unconfirmed'})
        with pytest.raises(HTTPException):safe.advance(c,job['id'])
        safe.put(c,'tiktok_bridge',bridge())
        c.execute('UPDATE safe_collection_batches SET created_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=150)).isoformat(),job['id']))
        with pytest.raises(HTTPException,match='Insufficient runtime'):safe.advance(c,job['id'])
