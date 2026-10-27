import json
from datetime import datetime,timezone,timedelta
import pytest
from fastapi import HTTPException
from app import db,safe_collection as safe
from test_product_detection import library
from test_controlled_stage2 import stage1_passed,authorize
from test_safe_collection import capture,EXT,confirm


def interrupted(detail='Error: Stage 2 session/page not healthy; stopped without retry'):
    ident=stage1_passed();queries=['home gadgets','home finds','useful home products'];authorize(ident,queries)
    with db.connect() as c:job=safe.start(c,ident,queries,2)
    db.claim_command(EXT);payload=capture('home gadgets');payload['page_url']='https://www.tiktok.com/search?q=home+gadgets'
    db.finish_command(job['command_id'],EXT,'SUCCEEDED','done',payload)
    with db.connect() as c:failed=safe.advance(c,job['id'])
    db.claim_command(EXT);db.finish_command(failed['command_id'],EXT,'FAILED',detail)
    with db.connect() as c:
        start=datetime.now(timezone.utc)-timedelta(hours=1)
        c.execute('UPDATE safe_collection_batches SET created_at=?,completed_at=? WHERE id=?',(start.isoformat(),(start+timedelta(seconds=10)).isoformat(),job['id']))
    return job,failed


def fresh(c):
    ident=safe.request_check(c,EXT)['id'];confirm(c,ident);return ident


def test_resume_same_batch_preserves_success_and_replay_is_idempotent(library):
    job,failed=interrupted()
    with db.connect() as c:
        before=dict(c.execute('SELECT * FROM safe_collection_batches WHERE id=?',(job['id'],)).fetchone())
        batch_count=c.execute('SELECT count(*) FROM safe_collection_batches').fetchone()[0]
        new=safe.resume_stage2(c,job['id'],fresh(c),EXT)
        replay=safe.resume_stage2(c,job['id'],'irrelevant-replay-check',EXT)
        assert replay['command_id']==new['command_id'] and replay['reused']
        after=dict(c.execute('SELECT * FROM safe_collection_batches WHERE id=?',(job['id'],)).fetchone())
        assert (after['seen'],after['new_videos'],after['snapshots'],after['created_at'])==(before['seen'],before['new_videos'],before['snapshots'],before['created_at'])
        assert c.execute('SELECT count(*) FROM safe_collection_batches').fetchone()[0]==batch_count
        assert c.execute('SELECT query FROM bridge_commands WHERE id=?',(new['command_id'],)).fetchone()[0]=='home finds'
        assert c.execute('SELECT count(*) FROM search_observations WHERE capture_id=?',(f"command:{job['command_id']}",)).fetchone()[0]==1
        assert 10<=safe.runtime_used(c,after)<12
    db.claim_command(EXT)
    payload=capture('home finds');payload['page_url']='https://www.tiktok.com/search?q=home+finds'
    payload['results'][0].update(video_id='124',video_url='https://www.tiktok.com/@maker/video/124')
    diag={'query':'home finds','pre_health':{'samples':[{},{}]},'navigation_state':'CAPTURED','settle_samples':[{},{}],'final_health':{'page':'healthy','session':'confirmed'},'stop_reason':'CAPTURE_COMPLETED'}
    for _ in range(2):assert db.finish_command(new['command_id'],EXT,'SUCCEEDED','stable capture',payload,search_diagnostics=diag)=='ok'
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM search_observations WHERE capture_id=?',(f"command:{new['command_id']}",)).fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM safe_search_diagnostics WHERE command_id=?',(new['command_id'],)).fetchone()[0]==1
        assert c.execute('SELECT status FROM bridge_commands WHERE id=?',(failed['command_id'],)).fetchone()[0]=='FAILED'
        next_job=safe.advance(c,job['id'])
        assert c.execute('SELECT query FROM bridge_commands WHERE id=?',(next_job['command_id'],)).fetchone()[0]=='useful home products'


@pytest.mark.parametrize('detail',['HTTP 403','captcha','LOGGED_OUT','SEARCH_ROUTE_INVALID_PERSISTENT','empty viewport','SESSION_NOT_STABLE; HTTP 403'])
def test_hard_or_unrelated_failures_cannot_resume(library,detail):
    job,_=interrupted(detail)
    with db.connect() as c:
        with pytest.raises(HTTPException):safe.resume_stage2(c,job['id'],fresh(c),EXT)
        assert not c.execute('SELECT 1 FROM safe_stage2_resumptions').fetchone()


def test_resume_preserves_remaining_new_video_budget(library):
    job,_=interrupted()
    with db.connect() as c:
        c.execute('UPDATE safe_collection_batches SET new_videos=29 WHERE id=?',(job['id'],))
        resumed=safe.resume_stage2(c,job['id'],fresh(c),EXT)
        options=json.loads(c.execute('SELECT options_json FROM bridge_commands WHERE id=?',(resumed['command_id'],)).fetchone()[0])
        assert options['max_results']==1 and options['max_scrolls']==0


def test_persisted_query_never_resumed_even_if_error_text_is_transient(library):
    job,failed=interrupted()
    with db.connect() as c:
        # An interrupted command with a saved observation cannot be replayed.
        c.execute('UPDATE search_observations SET capture_id=? WHERE capture_id=?',(f"command:{failed['command_id']}",f"command:{job['command_id']}"))
        with pytest.raises(HTTPException,match='already persisted'):safe.resume_stage2(c,job['id'],fresh(c),EXT)
