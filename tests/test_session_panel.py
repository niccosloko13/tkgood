from app import db
from app.session_api import connection_read_model
from test_dev_control import dev_api


def test_small_session_endpoint_is_read_only_and_exposes_queue_failure(dev_api):
    db.set_state('browser_security_stop',{'reason':'HTTP 403 historical'})
    code,_=dev_api('/api/bridge/heartbeat',{'extension_version':'0.1.6','companion_version':'0.1.6','api_version':'1','build_id':'1'*16,'command_api_status':404,'command_api_error':'API error: /api/dev/commands/next [404]'})
    assert code==200
    with db.connect() as c:
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        before={name:c.execute('SELECT count(*) FROM "'+name+'"').fetchone()[0] for name in tables}
    code,d=dev_api('/api/session/state')
    assert code==200 and d['bridge']['command_api_status']==404
    assert d['security_stop']['reason']=='HTTP 403 historical'
    assert d['renewal'] is None and d['check'] is None
    with db.connect() as c:
        assert tables==[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert before=={name:c.execute('SELECT count(*) FROM "'+name+'"').fetchone()[0] for name in before}


def test_heartbeat_recovery_is_visible_without_check_or_navigation(dev_api):
    for status in (404,200):
        dev_api('/api/bridge/heartbeat',{'extension_version':'0.1.6','command_api_status':status})
        assert dev_api('/api/session/state')[1]['bridge']['command_api_status']==status
    with db.connect() as c:
        assert c.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM safe_recovery_checks').fetchone()[0]==0


def test_connection_read_model_translates_internal_states_without_releasing_safety():
    healthy={'connected':True,'heartbeat_fresh':True,'chrome_connected':True,'tiktok_open':True,
             'current_page_status':'healthy','tiktok_session_status':'confirmed'}
    connected=connection_read_model(healthy,{})
    assert (connected['status'],connected['title'])==('CONNECTED','Conectado')
    missing_tab=connection_read_model({**healthy,'tiktok_open':False},{})
    assert (missing_tab['status'],missing_tab['title'])==('ATTENTION','TikTok não encontrado')
    offline=connection_read_model({**healthy,'connected':False},{})
    assert (offline['status'],offline['title'])==('DISCONNECTED','Navegador desconectado')
    login=connection_read_model({**healthy,'tiktok_session_status':'login_required'},{})
    assert (login['status'],login['title'])==('ATTENTION','Login necessário')
    blocked=connection_read_model(healthy,{'reason':'CAPTCHA'})
    assert (blocked['status'],blocked['title'],blocked['security'])==('BLOCKED','Ação necessária','BLOCKED')
