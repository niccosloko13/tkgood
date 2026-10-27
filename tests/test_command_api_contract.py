import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from app import db
from app.companion_contract import compatibility,contract
from test_dev_control import dev_api

@pytest.mark.parametrize('version,api,expected',[
    ('0.1.6','1','COMPATIBLE'),('0.1.5','1','COMPANION_DESATUALIZADO'),
    ('0.1.6','2','API_VERSION_MISMATCH'),('unknown','1','COMPANION_VERSION_UNCONFIRMED')])
def test_contract_compatibility(version,api,expected):
    assert compatibility({'companion_version':version,'api_version':api})['compatibility_status']==expected

def test_backend_routes_and_heartbeat_negotiation(dev_api):
    code,body=dev_api('/api/status');assert code==200 and body['api_version']=='1'
    assert body['companion_min_version']=='0.1.6'
    code,body=dev_api('/api/bridge/heartbeat',{'extension_version':'0.1.6','companion_version':'0.1.6','build_id':'1'*16,'api_version':'1'})
    assert code==200 and body['api_version']=='1' and body['dev_control_enabled']
    assert dev_api('/api/dev/commands/next')[0]==200
    bridge=dev_api('/api/bridge/state')[1];assert bridge['companion_compatible']

def test_renew_uses_existing_queue_and_verify_does_not_clear_stop(dev_api):
    stop={'reason':'HTTP 403: https://www.tiktok.com/','observed_at':'2026-01-01T00:00:00Z'}
    db.set_state('browser_security_stop',stop)
    dev_api('/api/bridge/heartbeat',{'extension_version':'0.1.6','companion_version':'0.1.6','build_id':'1'*16,'api_version':'1'})
    code,job=dev_api('/api/tiktok/renew',{});assert code==200
    assert dev_api('/api/dev/commands/next')[1]['command']['type']=='DEV_RENEW_TIKTOK_SESSION'
    dev_api('/api/dev/commands/'+job['id']+'/accept',{})
    dev_api('/api/dev/commands/'+job['id']+'/complete',{'status':'SUCCEEDED','build_id':'1'*16,'refreshed_tabs':0,'detail':'fixture renewal'})
    code,result=dev_api('/api/tiktok/verify',{});assert code==200 and result['status']=='UNKNOWN'
    assert db.get_state('browser_security_stop')['reason']==stop['reason']
    with db.connect() as c:assert c.execute('SELECT count(*) FROM bridge_commands').fetchone()[0]==0

def test_old_companion_is_reported_and_renew_refuses_it(dev_api):
    dev_api('/api/bridge/heartbeat',{'extension_version':'0.1.5','companion_version':'0.1.5','build_id':'1'*16})
    assert dev_api('/api/bridge/state')[1]['compatibility_status']=='COMPANION_DESATUALIZADO'
    assert dev_api('/api/tiktok/renew',{})[0]==409

def launcher():
    spec=importlib.util.spec_from_file_location('babi_launcher',Path('run.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_duplicate_babi_exits_without_starting_or_traceback(monkeypatch,capsys):
    m=launcher();monkeypatch.delenv('PH_RUN_ID',raising=False)
    monkeypatch.setattr(m,'existing_server',lambda p:{'kind':'babi'})
    assert m.main()==0
    assert 'Babi j\u00e1 est\u00e1 rodando' in capsys.readouterr().out

def test_other_listener_is_not_terminated(monkeypatch,capsys):
    m=launcher();monkeypatch.delenv('PH_RUN_ID',raising=False)
    monkeypatch.setattr(m,'existing_server',lambda p:{'kind':'other','owner':'PID 123 (fixture)'})
    assert m.main()==1
    assert 'PID 123' in capsys.readouterr().out
