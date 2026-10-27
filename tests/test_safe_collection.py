import json
from datetime import datetime,timezone,timedelta
import pytest
from fastapi import HTTPException
from app import db,safe_collection as safe,browser_safety
from app.observations import save_capture
from test_product_detection import library
from test_dev_control import dev_api

EXT='a'*32
def bridge(**changes):
    return dict(extension_id=EXT,build_id='1'*16,safe_collection_version='v1',current_url='https://www.tiktok.com/',tab_id=7,
        last_seen=safe.now(),page_ready_state='complete',current_page_status='healthy',tiktok_session_status='confirmed',
        session_evidence=['visible_own_profile_with_avatar','visible_account_inbox'],**changes)

def setup(c):
    safe.put(c,'browser_security_stop',{'reason':'HTTP 403: https://www.tiktok.com/','observed_at':'2026-01-01T00:00:00Z'})
    safe.put(c,'tiktok_bridge',bridge());return safe.request_check(c,EXT)['id']

def confirm(c,ident):
    c.execute('UPDATE safe_recovery_checks SET created_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=3)).isoformat(),ident))
    for i in range(2):
        b=bridge();b['last_seen']=(datetime.now(timezone.utc)-timedelta(seconds=1-i)).isoformat();safe.put(c,'tiktok_bridge',b);safe.observe_heartbeat(c,b)
    assert c.execute('SELECT status FROM safe_recovery_checks WHERE id=?',(ident,)).fetchone()[0]=='HEALTHY'

def capture(query='home organization'):
    return {'query':query,'page_url':'https://www.tiktok.com/search?q=home%20organization','results_count':1,'links_detected':1,
        'results':[{'video_url':'https://www.tiktok.com/@maker/video/123','video_id':'123','caption':'Soap dispenser','creator_username':'@maker','views_raw':'12K'}]}

def ready(c):
    ident=setup(c);confirm(c,ident);safe.release(c,ident,EXT)
    save_capture(c,capture(),'fixture:known',safe.now())
    return ident

@pytest.mark.parametrize('changes,status',[
    ({},'HEALTHY'),({'current_page_status':'http_403'},'BLOCKED'),({'current_page_status':'challenge'},'CHALLENGE'),
    ({'current_url':''},'UNKNOWN'),({'page_ready_state':'loading'},'UNKNOWN'),({'tiktok_session_status':'unconfirmed'},'UNKNOWN'),
    ({'session_evidence':[]},'UNKNOWN'),({'current_url':'https://www.tiktok.com/@maker/video/123'},'UNKNOWN'),
    ({'current_url':'https://www.tiktok.com.evil/search?q=x'},'UNKNOWN'),({'last_seen':'2026-01-01T00:00:00Z'},'UNKNOWN')])
def test_manual_health(changes,status):
    b=bridge();b.update(changes);assert safe.health(b,EXT,'1'*16)['status']==status

def test_check_never_unlatches_and_release_preserves_incident(library):
    with library.connect() as c:
        ident=setup(c);original=safe.state(c,'browser_security_stop');confirm(c,ident)
        assert safe.state(c,'browser_security_stop')==original
        assert c.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==0
        result=safe.release(c,ident,EXT)
        assert result['previous_incident']==original
        assert safe.state(c,'browser_security_history')['items'][-1]['validated_url']=='https://www.tiktok.com/'
        assert not safe.state(c,'browser_security_stop')
        assert safe.state(c,'safe_collection_guard')['enabled']
        with pytest.raises(HTTPException):safe.release(c,ident,EXT)

def test_unknown_cannot_release_and_new_incident_blocks_clear(library):
    with library.connect() as c:
        ident=setup(c)
        with pytest.raises(HTTPException):safe.release(c,ident,EXT)
        confirm(c,ident);safe.put(c,'browser_security_stop',{'reason':'new CAPTCHA'})
        with pytest.raises(HTTPException):safe.release(c,ident,EXT)

def test_single_capture_persists_dedup_trend_category_and_job_then_stops(library):
    with library.connect() as c:
        ident=ready(c);batch=safe.start(c,ident,['home organization']);command=batch['command_id']
    assert db.claim_command(EXT)['id']==command
    assert db.finish_command(command,EXT,'SUCCEEDED','Bounded capture',capture())=='ok'
    assert db.finish_command(command,EXT,'SUCCEEDED','Bounded capture',capture())=='ok'
    assert db.claim_command(EXT) is None
    with library.connect() as c:
        r=dict(c.execute('SELECT * FROM safe_collection_batches').fetchone())
        assert (r['status'],r['seen'],r['new_videos'],r['duplicates'],r['snapshots'])==('SUCCEEDED',1,0,1,1)
        assert c.execute('SELECT count(*) FROM videos').fetchone()[0]==1
        assert c.execute("SELECT count(*) FROM search_observations WHERE capture_id=?",(f'command:{command}',)).fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM video_category_classifications').fetchone()[0]==1
        assert c.execute("SELECT count(*) FROM intelligence_jobs WHERE job_type='identity'").fetchone()[0]==1
        with pytest.raises(HTTPException):safe.advance(c,r['id'])
        with pytest.raises(HTTPException):safe.start(c,ident,['home organization'])
    with pytest.raises(HTTPException):db.enqueue_search('other',EXT)

def test_stage1_hard_limit_and_stage2_requires_pass(library):
    with library.connect() as c:
        ident=ready(c)
        with pytest.raises(HTTPException):safe.start(c,ident,['home organization','second'])
        with pytest.raises(HTTPException):safe.start(c,ident,['home organization'],stage=2)
        with pytest.raises(HTTPException):safe.start(c,ident,['unobserved query'])
        safe.start(c,ident,['home organization'])
        with pytest.raises(HTTPException):safe.start(c,ident,['home organization'])

def test_server_rejects_over_limit_payload(library):
    with library.connect() as c:
        ident=ready(c);job=safe.start(c,ident,['home organization'])
    db.claim_command(EXT);payload=capture();payload['links_detected']=11
    assert db.finish_command(job['command_id'],EXT,'SUCCEEDED','bad limit',payload)=='conflict'
    with library.connect() as c:
        assert c.execute('SELECT count(*) FROM search_observations').fetchone()[0]==1

def test_security_incident_persists_and_stops_without_retry(library):
    with library.connect() as c:
        ident=ready(c);safe.start(c,ident,['home organization'])
    browser_safety.stop('CAPTCHA verify human',safe.now())
    assert db.claim_command(EXT) is None
    with library.connect() as c:
        assert c.execute('SELECT status FROM safe_collection_batches').fetchone()[0]=='BLOCKED'
        assert safe.state(c,'browser_security_stop')['reason']=='CAPTCHA verify human'
        assert c.execute("SELECT count(*) FROM bridge_commands WHERE status='FAILED'").fetchone()[0]==1

def test_api_check_unknown_has_no_navigation_or_automatic_clear(dev_api):
    db.set_state('browser_security_stop',{'reason':'HTTP 403: https://www.tiktok.com/'})
    code,result=dev_api('/api/dev/safe-recovery/checks',{})
    assert code==200 and result['status']=='UNKNOWN'
    assert dev_api('/api/dev/safe-recovery/checks/'+result['id']+'/release',{'operator_reviewed':True})[0]==409
    assert db.get_state('browser_security_stop')['reason'].startswith('HTTP 403')
    with db.connect() as c:assert c.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==0

def test_stage2_bounds_runtime_and_no_automatic_continuation(library):
    with library.connect() as c:
        ident=ready(c);stage1=safe.start(c,ident,['home organization'])
    db.claim_command(EXT);assert db.finish_command(stage1['command_id'],EXT,'SUCCEEDED','bounded',capture())=='ok'
    with library.connect() as c:
        with pytest.raises(HTTPException):safe.start(c,ident,['q'+str(i) for i in range(6)],2)
        stage2=safe.start(c,ident,['home organization'],2)
        assert stage2['max_results']==10
        with pytest.raises(HTTPException):safe.start(c,ident,['home organization'],2)
        c.execute("UPDATE safe_collection_batches SET created_at=? WHERE id=?",((datetime.now(timezone.utc)-timedelta(seconds=181)).isoformat(),stage2['id']))
    assert db.claim_command(EXT) is None

def test_stage2_remaining_new_video_budget_caps_next_viewport(library):
    with library.connect() as c:
        ident=ready(c);stage1=safe.start(c,ident,['home organization'])
    db.claim_command(EXT);db.finish_command(stage1['command_id'],EXT,'SUCCEEDED','bounded',capture())
    with library.connect() as c:
        # A paused batch with 28 genuine new items would have only 2 slots left.
        c.execute("INSERT INTO safe_collection_batches(id,stage,status,created_at,validation_id,queries_json,query_index,new_videos) VALUES ('fixture-stage2',2,'PAUSED',?,?,?,1,28)",(safe.now(),ident,json.dumps(['home organization']*2)))
        result=safe.advance(c,'fixture-stage2');assert result['max_results']==2

def test_expired_safe_command_stops_batch_without_retry(library):
    with library.connect() as c:
        ident=ready(c);job=safe.start(c,ident,['home organization'])
        c.execute('UPDATE bridge_commands SET created_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=46)).isoformat(),job['command_id']))
        db.expire_commands(c)
        row=c.execute('SELECT * FROM safe_collection_batches WHERE id=?',(job['id'],)).fetchone()
        assert row['status']=='FAILED' and row['stop_reason']=='COMMAND_TIMED_OUT_NO_RETRY'
        with pytest.raises(HTTPException):safe.advance(c,job['id'])
