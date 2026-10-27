import json
import pytest
from app import db
from app.browser_safety import authenticated_account_evidence
from test_dev_control import dev_api


@pytest.mark.parametrize('signals,accepted',[
    ({'profile_route_present':True,'messages_route_present':True},True),
    ({'profile_route_present':True,'account_avatar_present':True},False),
    ({'messages_route_present':True,'activity_or_inbox_present':True},False),
    ({'profile_route_present':True,'following_authenticated_present':True},True),
    ({'authenticated_sidebar_present':True},False),
    ({'profile_route_present':True,'messages_route_present':True,'logged_out_cta_present':True},False),
])
def test_independent_account_families(signals,accepted):
    assert authenticated_account_evidence({'session_signals':signals,'session_evidence':['visible_own_profile_with_avatar','visible_account_inbox']})==accepted


def test_real_wire_shape_confirms_without_avatar_and_preserves_stop(dev_api):
    stop={'reason':'HTTP 403 historical home','observed_at':'2026-01-01T00:00:00Z'}
    db.set_state('browser_security_stop',stop)
    signals={'profile_route_present':True,'messages_route_present':True,'account_avatar_present':False}
    code,_=dev_api('/api/bridge/heartbeat',{'extension_version':'0.1.6','companion_version':'0.1.6','api_version':'1','build_id':'1'*16,
        'current_url':'https://www.tiktok.com/','tab_id':7,'page_ready_state':'complete','current_page_status':'healthy','tiktok_session_status':'confirmed',
        'session_signals':signals,'session_evidence':['visible_account_inbox'],'session_detector_version':'dom-v2'})
    assert code==200
    state=dev_api('/api/session/state')[1]
    assert state['bridge']['tiktok_session_status']=='confirmed'
    assert state['security_stop']['reason']==stop['reason']
    with db.connect() as con:assert con.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==0


def test_probe_audit_uses_existing_dev_queue_and_rejects_changed_result(dev_api):
    dev_api('/api/bridge/heartbeat',{'extension_version':'0.1.6','build_id':'1'*16,'current_url':'https://www.tiktok.com/','tab_id':7})
    code,job=dev_api('/api/dev/commands',{'type':'DEV_INSPECT_TIKTOK_SESSION','expected_build':'1'*16});assert code==201
    assert dev_api('/api/dev/commands/'+job['id']+'/accept',{})[0]==200
    body={'status':'SUCCEEDED','build_id':'1'*16,'refreshed_tabs':0,'detail':'session-only audit','session_probe':{'mode':'READ_ONLY_SESSION_PROBE','url':'https://www.tiktok.com/','document_ready':'complete'}}
    route='/api/dev/commands/'+job['id']+'/complete'
    assert dev_api(route,body)[0]==200
    assert dev_api(route,body)[0]==200
    assert dev_api(route,{**body,'session_probe':{**body['session_probe'],'changed':True}})[0]==409
    with db.connect() as con:
        assert json.loads(con.execute('SELECT result_json FROM dev_commands WHERE id=?',(job['id'],)).fetchone()[0])['mode']=='READ_ONLY_SESSION_PROBE'
        assert con.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==0
