import json,os,subprocess,sys
from pathlib import Path
import pytest
from app import db
from scripts.process_runtime import hidden_kwargs
from test_capture import database,api


def test_removed_policy_api_and_state(api):
    _,call=api
    assert call('/api/quiet')[0]==404
    assert 'quiet' not in call('/api/status')[1]


def test_security_stop_is_persistent_blocks_claims_and_new_commands(api):
    from app.browser_safety import stop
    _,call=api
    call('/api/bridge/heartbeat',{'extension_version':'test','current_url':'https://www.tiktok.com/search?q=fixture'})
    job=db.enqueue_search('fixture','ext')
    stop('HTTP 403')
    assert db.claim_command('ext') is None
    assert next(r for r in db.list_commands() if r['id']==job)['status']=='FAILED'
    assert call('/api/commands',{'type':'SEARCH','query':'fixture'})[0]==409
    assert call('/api/tiktok/open',{})[1]['ok'] is False
    assert call('/api/status')[1]['security_stop']['reason']=='HTTP 403'
    db.init_db()
    assert db.get_state('browser_security_stop')['reason']=='HTTP 403'


def test_chrome_reuses_live_profile_without_spawning(database,monkeypatch):
    from app import chrome_launcher as launcher
    monkeypatch.setattr(launcher,'profile_processes',lambda:[123])
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:pytest.fail('must reuse Chrome'))
    for _ in range(2):
        assert launcher.open_tiktok_in_normal_chrome()['reused'] is True


def test_chrome_opens_once_then_reuses_and_inventory_failure_refuses_duplicate(database,monkeypatch,tmp_path):
    from app import chrome_launcher as launcher
    calls=[]
    monkeypatch.setattr(launcher,'CHROME_PROFILE_DIR',tmp_path/'profile')
    monkeypatch.setattr(launcher,'find_chrome',lambda:tmp_path/'chrome.exe')
    monkeypatch.setattr(launcher,'profile_processes',lambda:[123] if calls else [])
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k:calls.append((a,k)))
    assert launcher.open_tiktok_in_normal_chrome()['reused'] is False
    assert launcher.open_tiktok_in_normal_chrome()['reused'] is True
    assert len(calls)==1
    assert calls[0][1]['stderr']==subprocess.STDOUT
    def unavailable():
        raise OSError('inventory unavailable')
    monkeypatch.setattr(launcher,'profile_processes',unavailable)
    assert launcher.open_tiktok_in_normal_chrome()['ok'] is False
    assert len(calls)==1


def test_legacy_waiting_migration_preserves_ids_and_never_replays(tmp_path,monkeypatch):
    import sqlite3
    path=tmp_path/'legacy.db'
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE bridge_commands(id INTEGER PRIMARY KEY,created_at TEXT,updated_at TEXT,type TEXT,query TEXT,status TEXT CHECK(status IN ('PENDING','WAITING_FOR_VISIBLE_BROWSER')),extension_id TEXT,detail TEXT)")
        con.execute("INSERT INTO bridge_commands VALUES (91,'2000','2000','SEARCH','original','WAITING_FOR_VISIBLE_BROWSER','ext','original detail')")
    monkeypatch.setattr(db,'DB_PATH',path)
    db.init_db();db.init_db()
    with db.connect() as con:
        row=dict(con.execute('SELECT * FROM bridge_commands WHERE id=91').fetchone())
    assert row['status']=='FAILED' and row['detail']=='original detail' and row['query']=='original'
    assert db.claim_command('ext') is None

def test_windows_children_have_no_console_and_hidden_startup():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    options=hidden_kwargs()
    if os.name=='nt':
        assert options['creationflags'] & subprocess.CREATE_NO_WINDOW
        assert not options['creationflags'] & subprocess.DETACHED_PROCESS
        assert options['startupinfo'].dwFlags & subprocess.STARTF_USESHOWWINDOW
        assert options['startupinfo'].wShowWindow==0


@pytest.mark.skipif(os.name!='nt',reason='Windows console verification')
def test_real_child_has_no_console_and_preserves_stdout_stderr(tmp_path):
    destination=tmp_path/'child.log'
    with destination.open('wb') as log:
        result=subprocess.run([sys.executable,'-c',
            'import ctypes,sys; print("console="+str(ctypes.windll.kernel32.GetConsoleWindow())); print("stderr preserved",file=sys.stderr)'],
            stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,**hidden_kwargs())
    assert result.returncode==0
    assert 'console=0' in destination.read_text()
    assert 'stderr preserved' in destination.read_text()


def test_migration_preserves_old_command_values(tmp_path,monkeypatch):
    import sqlite3
    path=tmp_path/'old.db'
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE bridge_commands(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,type TEXT NOT NULL,query TEXT NOT NULL,status TEXT NOT NULL,extension_id TEXT NOT NULL,detail TEXT NOT NULL,result_hash TEXT NOT NULL,options_json TEXT NOT NULL)")
        con.execute("INSERT INTO bridge_commands VALUES (81,'2000','2000','READ_CREATOR_PROFILE','profile','SUCCEEDED','ext','original','hash','{}')")
    monkeypatch.setattr(db,'DB_PATH',path)
    db.init_db()
    db.init_db()
    with db.connect() as con:
        row=dict(con.execute('SELECT * FROM bridge_commands').fetchone())
        assert row['id']==81 and row['detail']=='original' and row['result_hash']=='hash'
        assert row['status']=='SUCCEEDED' and row['ready_at']=='2000'


def test_fixed_background_launcher_logs_spawn_errors(tmp_path,monkeypatch):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    import background_runner
    monkeypatch.setattr(background_runner,'ROOT',tmp_path)
    with pytest.raises(ValueError):
        background_runner.launch('arbitrary-shell',[])
    def fail(*args,**kwargs):
        if os.name=='nt':
            assert kwargs['creationflags'] & subprocess.CREATE_NO_WINDOW
        assert kwargs['stderr']==subprocess.STDOUT
        raise OSError('fixture launch denied')
    monkeypatch.setattr(subprocess,'Popen',fail)
    with pytest.raises(OSError):
        background_runner.launch('devctl',['status'])
    record=json.loads(next((tmp_path/'.runtime/logs').glob('task-*.json')).read_text())
    assert record['status']=='FAILED' and record['exit_code']==1
    assert record['error']=='fixture launch denied'
