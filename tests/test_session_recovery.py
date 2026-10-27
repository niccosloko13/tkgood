import json
import os
from datetime import datetime,timezone,timedelta
import pytest
from app import db,browser_safety
from app.main import live_bridge
from test_dev_control import dev_api


def home(incident):
    return {'extension_id':'a'*32,'build_id':'1'*16,'current_url':'https://www.tiktok.com/',
        'current_page_status':'healthy','tiktok_session_status':'confirmed','page_ready_state':'complete',
        'session_evidence':['visible_own_profile_with_avatar','visible_account_inbox'],
        'last_seen':datetime.now(timezone.utc).isoformat()}


def validation(call,incident):
    db.set_state('browser_security_stop',incident)
    _,job=call('/api/dev/commands',{'type':'DEV_VALIDATE_TIKTOK_HOME','expected_build':'1'*16})
    assert call('/api/dev/commands/'+job['id']+'/accept',{})[0]==200
    db.set_state('tiktok_bridge',home(incident))
    assert call('/api/dev/commands/'+job['id']+'/complete',{
        'status':'SUCCEEDED','build_id':'1'*16,'refreshed_tabs':1,'detail':'healthy home'})[0]==200
    return '/api/dev/recovery/'+job['id']+'/clear-reviewed-stop'


@pytest.fixture
def incident():
    return {'reason':'HTTP 403: https://www.tiktok.com/@maker/video/123','observed_at':'2026-10-22T12:00:00Z'}


def test_controlled_clear_requires_home_evidence_and_preserves_history(dev_api,incident):
    route=validation(dev_api,incident)
    assert db.get_state('browser_security_stop')['reason']==incident['reason']
    assert dev_api(route,{})[0]==200
    assert not db.get_state('browser_security_stop').get('reason')
    assert db.get_state('browser_security_history')['items'][-1]['page_failure']=='isolated_403'
    assert db.get_state('browser_security_clearance')['observed_at']==incident['observed_at']
    assert dev_api(route,{})[0]==409


@pytest.mark.parametrize('change',[
    {'current_url':'https://www.tiktok.com/@maker/video/123'},
    {'current_page_status':'http_403'},{'current_page_status':'challenge'},
    {'tiktok_session_status':'unconfirmed'},{'tiktok_session_status':'login_required'},
    {'session_evidence':[]},{'extension_id':'other'},
    {'page_ready_state':'loading'},
    {'last_seen':(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()},
])
def test_clear_refuses_stale_unconfirmed_wrong_route_or_challenge(dev_api,incident,change):
    route=validation(dev_api,incident)
    db.set_state('tiktok_bridge',{**home(incident),**change})
    assert dev_api(route,{})[0]==409
    assert db.get_state('browser_security_stop')['reason']==incident['reason']


def test_new_security_incident_prevents_clearing_old_one(dev_api,incident):
    route=validation(dev_api,incident)
    browser_safety.stop('HTTP 403: https://www.tiktok.com/','2026-10-23T12:00:00Z')
    assert dev_api(route,{})[0]==409
    assert db.get_state('browser_security_stop')['reason'].endswith('https://www.tiktok.com/')
    assert db.get_state('browser_security_history')['items'][0]['reason']==incident['reason']


def test_home_recovery_does_not_accept_challenge_latch(dev_api):
    db.set_state('browser_security_stop',{'reason':'captcha','observed_at':'2026-10-22T12:00:00Z'})
    assert dev_api('/api/dev/commands',{'type':'DEV_VALIDATE_TIKTOK_HOME','expected_build':'1'*16})[0]==409


def test_stale_heartbeat_never_confirms_current_session(dev_api,incident):
    db.set_state('tiktok_bridge',{**home(incident),'last_seen':'2026-10-22T12:00:00+00:00'})
    state=live_bridge()
    assert not state['companion_connected'] and not state['heartbeat_fresh']
    assert state['tiktok_session_status']=='unconfirmed' and state['current_page_status']=='unknown'


def test_replayed_old_latch_after_clear_is_acked_but_new_403_is_not_ignored(dev_api,incident):
    route=validation(dev_api,incident)
    assert dev_api(route,{})[0]==200
    payload={'current_url':'https://www.tiktok.com/','security_stop':incident['reason'],
             'security_stop_observed_at':incident['observed_at']}
    assert dev_api('/api/bridge/heartbeat',payload)[0]==200
    assert not db.get_state('browser_security_stop').get('reason')
    payload['security_stop_observed_at']='2026-10-23T12:00:00Z'
    assert dev_api('/api/bridge/heartbeat',payload)[0]==200
    assert db.get_state('browser_security_stop')['observed_at']==payload['security_stop_observed_at']


def test_runner_uses_actual_bridge_readiness_contract(monkeypatch):
    from app import main,night_discovery
    bridge={'tiktok_session_status':'confirmed','current_page_status':'healthy',
            'url':'https://www.tiktok.com/search?q=home+organization',
            'page_signals':{'content_script_connected':True,'ready_state':'complete'}}
    monkeypatch.setattr(main,'live_bridge',lambda:bridge)
    adapter=night_discovery.Adapter()
    assert adapter.ready('home organization')
    assert not adapter.ready('other query')
    bridge['tiktok_session_status']='unconfirmed'
    assert not adapter.ready('home organization')


def test_backend_does_not_trust_a_confirmation_without_account_evidence(dev_api):
    assert dev_api('/api/bridge/heartbeat',{'current_url':'https://www.tiktok.com/',
        'current_page_status':'healthy','tiktok_session_status':'confirmed','page_ready_state':'complete',
        'authenticated_hint':True})[0]==200
    assert live_bridge()['tiktok_session_status']=='unconfirmed'
    assert not live_bridge()['authenticated_hint']


@pytest.mark.skipif(os.name!='nt',reason='Windows existing-profile bootstrap')
def test_bootstrap_refuses_a_second_chrome_when_companion_profile_is_absent(tmp_path,monkeypatch):
    import bootstrap_companion as bootstrap
    from dev_supervisor import DevError
    monkeypatch.setattr(bootstrap.subprocess,'check_output',lambda *a,**k:'[]')
    monkeypatch.setattr(bootstrap.subprocess,'Popen',lambda *a,**k:pytest.fail('Must not launch another Chrome'))
    with pytest.raises(DevError,match='refusing to open another Chrome'):
        bootstrap.bootstrap(tmp_path)
