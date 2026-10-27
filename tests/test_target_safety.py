import json
from datetime import datetime,timezone,timedelta
import pytest
from fastapi import HTTPException
from app import db,safe_collection as safe,target_safety as ts,browser_safety
from test_product_detection import library
from test_dev_control import dev_api
from test_safe_collection import bridge,ready,confirm
from test_safe_collection import capture

URL='https://www.tiktok.com/@maker/video/123'


def stamp(offset=0):return (datetime.now(timezone.utc)+timedelta(seconds=offset)).isoformat()


def healthy():db.set_state('tiktok_bridge',bridge())


def test_video_403_waits_then_quarantines_without_global_stop(library):
    # Previous success is insufficient; no navigation is allowed in the gap.
    db.set_state('tiktok_bridge',{**bridge(),'last_seen':stamp(-10)})
    event=stamp(-1)
    assert ts.report_403(URL,event)['classification']=='TARGET_PENDING_HEALTH'
    assert db.claim_command('a'*32) is None
    assert not db.get_state('browser_security_stop',{}).get('reason')
    with db.connect() as c:
        assert ts.blocked(c,URL+'?tracking=ignored')
        assert ts.classify_pending(c,bridge()) is None
        assert not safe.state(c,'target_security_pending').get('items')
        row=ts.rows(c)[0];assert (row['target_type'],row['reason'],row['status'],row['attempt_count'])==('VIDEO','HTTP_403','BLOCKED',1)
    assert not db.get_state('browser_security_stop',{}).get('reason')


def test_same_blocked_target_rejected_before_dispatch_and_attempt_not_inflated(library):
    healthy();event=stamp(-1);ts.report_403(URL,event);ts.report_403(URL,event)
    with pytest.raises(HTTPException,match='TARGET_PREVIOUSLY_BLOCKED'):
        db.enqueue_command('READ_VIDEO_DETAIL',URL,'a'*32)
    with pytest.raises(HTTPException,match='TARGET_PREVIOUSLY_BLOCKED'):
        db.enqueue_command('READ_VIDEO_DETAIL','https://www.tiktok.com/@renamed/video/123','a'*32)
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==0
        assert ts.rows(c)[0]['attempt_count']==1


def test_search_capture_retains_blocked_reference_and_other_results_without_detail_commands(library):
    with db.connect() as c:
        ident=ready(c);ts.quarantine(c,URL,stamp(-1));job=safe.start(c,ident,['home organization'])
    assert db.claim_command('a'*32)['id']==job['command_id']
    payload=capture();base=payload['results'][0]
    payload['results']=[{**base,'video_id':str(i),'video_url':f'https://www.tiktok.com/@maker/video/{i}'} for i in (122,123,124)]
    payload['results_count']=payload['links_detected']=3
    assert db.finish_command(job['command_id'],'a'*32,'SUCCEEDED','search only',payload)=='ok'
    with db.connect() as c:
        refs=list(c.execute('SELECT video_id FROM search_observations WHERE capture_id=?',(f"command:{job['command_id']}",)))
        assert len(refs)==3
        assert c.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==1
        assert not safe.state(c,'browser_security_stop').get('reason')


@pytest.mark.parametrize('url',['https://www.tiktok.com/','https://www.tiktok.com/search?q=home+gadgets','https://www.tiktok.com/login','https://www.tiktok.com/challenge','https://www.tiktok.com/captcha','https://www.tiktok.com/verify','https://www.tiktok.com/api/general'])
def test_general_403_is_global(library,url):
    healthy();assert ts.report_403(url,stamp())['classification']=='GLOBAL_BLOCK'
    assert db.get_state('browser_security_stop')['reason'].startswith('HTTP 403:')


def test_challenge_is_never_downgraded(library):
    healthy();browser_safety.stop('CAPTCHA verify human',stamp(-2))
    assert ts.report_403(URL,stamp(-1))['classification']=='GLOBAL_BLOCK'
    assert db.get_state('browser_security_stop')['reason']=='CAPTCHA verify human'


@pytest.mark.parametrize('change',[
    {'current_url':'https://www.tiktok.com/challenge'},
    {'current_page_status':'challenge'},
    {'current_page_status':'http_403'},
    {'tiktok_session_status':'login_required'},
])
def test_global_detector_evidence_blocks_even_without_pending_target(change):
    assert ts.general_block_reason({**bridge(),**change}).startswith('GLOBAL_BLOCK:')


def test_target_http_403_is_not_global_detector_evidence():
    assert ts.general_block_reason({**bridge(),'current_url':URL,'current_page_status':'http_403','tiktok_session_status':'unconfirmed'}) is None


def test_three_distinct_targets_trip_global_circuit_and_repeats_do_not(library):
    healthy()
    for i in range(3):
        result=ts.report_403(URL,stamp(-5+i))
        assert result['classification']=='TARGET_BLOCK'
    assert not db.get_state('browser_security_stop',{}).get('reason')
    assert ts.report_403('https://www.tiktok.com/@renamed/video/123',stamp(-1))['classification']=='TARGET_BLOCK'
    assert ts.report_403('https://www.tiktok.com/@maker/video/124',stamp(-1))['classification']=='TARGET_BLOCK'
    assert ts.report_403('https://www.tiktok.com/@other',stamp(-1))['classification']=='GLOBAL_BLOCK'
    assert 'three distinct targets' in db.get_state('browser_security_stop')['reason']


def test_expired_target_event_does_not_trip_short_window(library):
    healthy();ts.report_403(URL,stamp(-1))
    with db.connect() as c:c.execute('UPDATE target_block_events SET received_at=?',(stamp(-ts.WINDOW_SECONDS-10),))
    assert ts.report_403('https://www.tiktok.com/@maker/video/124',stamp(-1))['classification']=='TARGET_BLOCK'
    assert ts.report_403('https://www.tiktok.com/@maker/video/125',stamp(-1))['classification']=='TARGET_BLOCK'


@pytest.mark.parametrize('change',[{'current_page_status':'http_403'},{'current_page_status':'challenge'},{'tiktok_session_status':'login_required'}])
def test_passive_home_failure_or_session_degradation_promotes_global(library,change):
    db.set_state('tiktok_bridge',{**bridge(),'last_seen':stamp(-10)})
    ts.report_403(URL,stamp(-1))
    with db.connect() as c:reason=ts.classify_pending(c,{**bridge(),**change})
    assert reason.startswith('GLOBAL_BLOCK:')


def test_target_page_still_403_requires_home_evidence_without_auto_navigation(library):
    db.set_state('tiktok_bridge',{**bridge(),'current_url':URL,'current_page_status':'http_403'})
    assert ts.report_403(URL,stamp(-1))['classification']=='TARGET_PENDING_HEALTH'
    assert not db.get_state('browser_security_stop',{}).get('reason')


def test_current_exact_target_latch_archived_only_after_healthy_home(library):
    event=stamp(-1);browser_safety.stop('HTTP 403: '+URL,event);healthy()
    assert ts.report_403(URL,event)['classification']=='TARGET_BLOCK'
    assert not db.get_state('browser_security_stop',{}).get('reason')
    assert db.get_state('browser_security_clearance')['observed_at']==event
    assert db.get_state('browser_security_history')['items'][-1]['classification']=='TARGET_BLOCK'


def test_new_search_only_authorization_preserves_history_and_cannot_start_stage2(library):
    with db.connect() as c:
        prior=ready(c)
        safe.put(c,'browser_security_history',{'items':[{'reason':'old incident'}]})
        ident=safe.request_check(c,'a'*32)['id'];confirm(c,ident)
        safe.authorize_healthy_stage1(c,ident,'a'*32)
        assert safe.state(c,'browser_security_history')['items']==[{'reason':'old incident'}]
        with pytest.raises(HTTPException):safe.start(c,ident,['home organization'],2)
        job=safe.start(c,ident,['home organization'])
        options=json.loads(c.execute('SELECT options_json FROM bridge_commands WHERE id=?',(job['command_id'],)).fetchone()[0])
        assert options['max_results']==10 and options['max_scrolls']==0
        with pytest.raises(HTTPException):safe.start(c,ident,['home organization'])


def test_failure_endpoint_requires_companion_identity_and_sanitizes_params(dev_api):
    db.set_state('tiktok_bridge',bridge())
    assert dev_api('/api/bridge/target-403',{'extension_id':'other','url':URL,'observed_at':stamp()})[0]==403
    code,result=dev_api('/api/bridge/target-403',{'extension_id':'a'*32,'url':URL+'?token=secret','observed_at':stamp(-1)})
    assert code==200 and result['classification']=='TARGET_BLOCK'
    assert 'secret' not in json.dumps(result)
