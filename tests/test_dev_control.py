import contextlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest
import uvicorn
from app import db, dev_control
from app.main import app

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from dev_supervisor import Supervisor, DevError, identity, atomic_json, build_extension
from devctl import bridge_ready, wait_until
from bootstrap_companion import dedicated_roots


@pytest.fixture
def dev_api(tmp_path, monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'test.db')
    monkeypatch.setattr(dev_control,'ROOT',tmp_path)
    monkeypatch.setenv('PH_DEV_CONTROL','1')
    (tmp_path/'.runtime').mkdir()
    (tmp_path/'.runtime/dev.json').write_text(json.dumps({'token':'test-token','extension_id':'a'*32}))
    db.init_db()
    db.set_state('tiktok_bridge',{'extension_id':'a'*32})
    sock=socket.socket(); sock.bind(('127.0.0.1',0))
    server=uvicorn.Server(uvicorn.Config(app,lifespan='off',log_level='error'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True); thread.start()
    deadline=time.monotonic()+5
    while not server.started and time.monotonic()<deadline: time.sleep(.01)
    assert server.started
    def call(path, payload=None, **headers):
        req=Request(f'http://127.0.0.1:{sock.getsockname()[1]}'+path,
                    data=json.dumps(payload).encode() if payload is not None else None,
                    headers={'Content-Type':'application/json','X-PH-Dev-Token':'test-token','X-Extension-ID':'a'*32,**headers})
        try:
            with urlopen(req,timeout=4) as response: return response.status,json.load(response)
        except HTTPError as error: return error.code,json.load(error)
    try: yield call
    finally:
        server.should_exit=True; thread.join(5); sock.close()


def test_dev_auth_schemas_and_lifecycle(dev_api,monkeypatch):
    call=dev_api
    assert call('/api/dev/status',**{'X-PH-Dev-Token':'bad'})[0]==403
    assert call('/api/dev/status',Origin='https://evil.example')[0]==403
    assert call('/api/dev/status',Host='evil.example')[0]==403
    assert call('/api/dev/commands/next',**{'X-Extension-ID':'b'*32})[0]==403
    assert call('/api/dev/commands',{'type':'LIKE','expected_build':'1'*16})[0]==422
    code,command=call('/api/dev/commands',{'type':'DEV_RELOAD_EXTENSION','expected_build':'1'*16})
    assert code==201
    assert call('/api/dev/commands/next')[1]['command']['id']==command['id']
    complete={'status':'SUCCEEDED','build_id':'1'*16,'refreshed_tabs':1,'detail':'ready'}
    route='/api/dev/commands/'+command['id']
    assert call(route+'/complete',complete)[0]==409
    assert call(route+'/accept',{})[0]==200
    assert call(route+'/accept',{})[0]==200
    assert call(route+'/complete',{**complete,'build_id':'2'*16})[0]==409
    assert call(route+'/complete',complete)[0]==200
    assert call(route+'/complete',complete)[0]==200
    assert call(route+'/complete',{**complete,'refreshed_tabs':2})[0]==409
    assert call('/api/dev/status')[1]['jobs'][0]['status']=='SUCCEEDED'
    monkeypatch.delenv('PH_DEV_CONTROL')
    assert call('/api/dev/status')[0]==404


def test_maintenance_preserves_active_capture_and_expires_dev_jobs(dev_api):
    call=dev_api
    ident=db.enqueue_search('home gadgets','a'*32)
    db.claim_command('a'*32)
    assert call('/api/dev/drain',{})[1]['commands'][0]['id']==ident
    assert call('/api/dev/commands',{'type':'DEV_REFRESH_TIKTOK','expected_build':'1'*16})[0]==409
    assert call('/api/dev/shutdown',{})[0]==409
    with pytest.raises(Exception) as error: db.enqueue_search('new','a'*32)
    assert error.value.status_code==409
    assert db.finish_command(ident,'a'*32,'SUCCEEDED','ready')=='ok'
    assert not call('/api/dev/status')[1]['active']['commands']
    _,command=call('/api/dev/commands',{'type':'DEV_REFRESH_TIKTOK','expected_build':'1'*16})
    with db.connect() as con:
        con.execute("UPDATE dev_commands SET created_at='2000-01-01T00:00:00+00:00' WHERE id=?",(command['id'],))
    assert call('/api/dev/status')[1]['jobs'][0]['status']=='EXPIRED'
    assert call('/api/dev/resume',{})[0]==200
    db.enqueue_search('new','a'*32)


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); return sock.getsockname()[1]


def test_supervisor_ownership_start_restart_and_health(tmp_path):
    # A real child HTTP process on an ephemeral port; production DB/8000 untouched.
    runner=tmp_path/'run.py'
    runner.write_text('''import os,json,threading
from http.server import BaseHTTPRequestHandler,HTTPServer
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self):
  data=({'app':'online','mode':'normal_chrome_bridge'} if self.path=='/api/status' else {'run_id':os.environ['PH_RUN_ID'],'active':{'commands':[],'missions':[]}})
  self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(data).encode())
 def do_POST(self):
  self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
  if self.path=='/api/dev/shutdown': threading.Thread(target=self.server.shutdown).start()
server=HTTPServer(('127.0.0.1',int(os.environ['PH_PORT'])),Handler)
server.serve_forever()
server.server_close()
''')
    supervisor=Supervisor(root=tmp_path,port=free_port())
    first=None
    try:
        with supervisor.lock():
            first=supervisor.start(timeout=10)
            assert first['identity']==identity(first['pid'])
            assert supervisor.start(timeout=2)['pid']==first['pid']
            with pytest.raises(DevError,match='Another devctl'):
                with supervisor.lock(): pass
            second=supervisor.restart()
            assert second['run_id']!=first['run_id']
            assert identity(first['pid']) is None
            assert supervisor.healthy()
            original=json.loads(supervisor.record_path.read_text())
            altered={**original,'identity':{'created':'forged','executable':'other'}}
            atomic_json(supervisor.record_path,altered)
            with pytest.raises(DevError,match='unmanaged'): supervisor.stop()
            atomic_json(supervisor.record_path,original)
            supervisor.stop()
            assert not supervisor.healthy()
        assert 'Supervisor starting' in (supervisor.runtime/'logs/backend.log').read_text()
    finally:
        if supervisor.record(): supervisor.stop()


def test_supervisor_refuses_unmanaged_listener_and_health_timeout(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); sock.listen()
        supervisor=Supervisor(root=tmp_path,port=sock.getsockname()[1])
        with pytest.raises(DevError,match='unmanaged'): supervisor.start()
        assert not supervisor.record_path.exists()
    supervisor=Supervisor(root=tmp_path,port=free_port())
    with pytest.raises(DevError,match='Health timeout'): supervisor.wait_health('unknown',timeout=.01)


def test_devctl_timeout_and_fresh_reconnection():
    from datetime import datetime,timezone,timedelta
    since=datetime.now(timezone.utc)
    status={'bridge':{'connected':True,'tiktok_open':True,'build_id':'1'*16,'page_signals':{'content_script_connected':True},'last_seen':since.isoformat()}}
    assert bridge_ready(status,'1'*16,since)
    assert not bridge_ready(status,'2'*16,since)
    assert not bridge_ready(status,'1'*16,since+timedelta(seconds=1))
    status['bridge']['page_signals']['content_script_connected']=False
    assert not bridge_ready(status,'1'*16,since)
    with pytest.raises(DevError,match='Timeout'): wait_until(lambda:False,.01,'bridge reconnect')


def test_bootstrap_selects_only_the_dedicated_browser_root(tmp_path):
    profile=tmp_path/'profile'
    processes=[{'ProcessId':1,'ExecutablePath':'chrome.exe','CommandLine':f'chrome.exe|--user-data-dir={profile}'},
        {'ProcessId':2,'ExecutablePath':'chrome.exe','CommandLine':'chrome.exe|--user-data-dir=personal'},
        {'ProcessId':3,'ExecutablePath':'chrome.exe','CommandLine':f'chrome.exe|--user-data-dir={profile}|--type=renderer'},
        {'ProcessId':4,'ExecutablePath':'other.exe','CommandLine':f'other.exe|--user-data-dir={profile}'}]
    assert [p['ProcessId'] for p in dedicated_roots(processes,profile,lambda s:s.split('|'))]==[1]


def test_heartbeat_build_metadata_is_optional_and_preserved(dev_api):
    code,_=dev_api('/api/bridge/heartbeat',{'extension_version':'0.1.4','companion_version':'0.1.4','build_id':'f'*16})
    assert code==200
    bridge=dev_api('/api/status')[1]['bridge']
    assert bridge['build_id']=='f'*16
    assert bridge['companion_version']=='0.1.4'
    assert dev_api('/api/bridge/heartbeat',{'build_id':'unbounded text'})[0]==422


def test_build_identity_tracks_code_but_never_local_secrets(tmp_path):
    extension=tmp_path/'extension'; extension.mkdir()
    (extension/'background.js').write_text('version-one')
    first=build_extension(tmp_path)
    assert len(first)==16
    assert build_extension(tmp_path)==first
    (extension/'dev_config.js').write_text('secret-local-token')
    assert build_extension(tmp_path)==first
    (extension/'background.js').write_text('version-two')
    assert build_extension(tmp_path)!=first
