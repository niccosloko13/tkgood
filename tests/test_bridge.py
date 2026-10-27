from scripts.process_runtime import hidden_kwargs
import json
import threading
import socket
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest
import uvicorn
from pydantic import ValidationError
from app import db
from app.main import app, live_bridge
from app.schemas import SearchCommand, CommandResult, BridgeHeartbeat


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'test.db')
    db.init_db()


def test_schemas():
    assert SearchCommand(query='  home   gadgets ').query == 'home gadgets'
    for payload in ({'query': ' '}, {'query': 123}, {'query': 'x', 'type': 'LIKE'}, {'query': 'x', 'selector': 'button'}, {'query': 'x' * 201}):
        with pytest.raises(ValidationError):
            SearchCommand(**payload)
    for status in ('PENDING', 'DISPATCHED', 'EXPIRED', 'like'):
        with pytest.raises(ValidationError):
            CommandResult(extension_id='test', status=status)


def test_heartbeat_defaults():
    heartbeat = BridgeHeartbeat()
    assert heartbeat.current_url == ''
    assert heartbeat.page_title is None
    assert heartbeat.page_ready_state is None
    assert not heartbeat.authenticated_hint
    assert not heartbeat.has_search_ui
    assert not heartbeat.playback_error_visible


def extension_heartbeat(*args):
    script = Path(__file__).with_name('heartbeat_payload.cjs')
    return json.loads(subprocess.check_output(['node', str(script), *args], text=True, timeout=10, **hidden_kwargs()))


def test_stale_bridge(isolated_db):
    db.set_state('tiktok_bridge', {'last_seen': (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat(), 'chrome_connected': True, 'tiktok_open': True, 'authenticated_hint': True})
    assert not live_bridge()['connected']
    assert not live_bridge()['authenticated_hint']
    assert not live_bridge()['tiktok_open']


def test_command_transitions(isolated_db):
    command_id = db.enqueue_search('home gadgets', 'ext')
    assert db.claim_command('other') is None
    assert db.finish_command(command_id, 'ext', 'SUCCEEDED', '') == 'conflict'
    assert db.claim_command('ext')['status'] == 'DISPATCHED'
    assert db.claim_command('ext') is None
    assert db.finish_command(command_id, 'other', 'SUCCEEDED', '') == 'missing'
    assert db.finish_command(command_id, 'ext', 'SUCCEEDED', 'navigation accepted') == 'ok'
    assert db.finish_command(command_id, 'ext', 'SUCCEEDED', 'navigation accepted') == 'ok'
    assert db.finish_command(command_id, 'ext', 'FAILED', '') == 'conflict'
    failed = db.enqueue_search('test', 'ext')
    db.claim_command('ext')
    assert db.finish_command(failed, 'ext', 'FAILED', 'tab closed') == 'ok'
    expired = db.enqueue_search('old', 'ext')
    with db.connect() as con:
        con.execute('UPDATE bridge_commands SET created_at=? WHERE id=?', ((datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat(), expired))
    assert db.list_commands()[0]['status'] == 'EXPIRED'
    assert db.finish_command(expired, 'ext', 'SUCCEEDED', '') == 'conflict'


def test_http_bridge_on_temporary_port(isolated_db):
    # Real HTTP validation, isolated database and port; never touch port 8000.
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    import time
    deadline = time.monotonic() + 5
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.01)
    assert server.started
    base = f'http://127.0.0.1:{sock.getsockname()[1]}'

    def call(path, payload=None):
        req = Request(base + path, data=json.dumps(payload).encode() if payload is not None else None, headers={'Content-Type': 'application/json', 'X-Extension-ID': 'ext'})
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    try:
        assert call('/api/commands', {'query': 'gadgets'})[0] == 409
        payload = extension_heartbeat()
        assert set(payload) == {'security_stop_observed_at','current_page_status','tiktok_session_status','session_evidence','window_state','window_width','window_height','tab_active','tab_id','window_id','tiktok_tab_count','document_visibility','security_stop','extension_version', 'current_url', 'page_title', 'authenticated_hint', 'page_ready_state', 'has_search_ui', 'playback_error_visible'}
        assert payload == {'security_stop_observed_at':None,'current_page_status':'unknown','tiktok_session_status':'unconfirmed','session_evidence':[],'window_state':None,'window_width':None,'window_height':None,'tab_active':None,'tab_id':7,'window_id':None,'tiktok_tab_count':1,'document_visibility':None,'security_stop':None,'extension_version': '0.1.4', 'current_url': 'https://www.tiktok.com/', 'page_title': 'TikTok', 'authenticated_hint': False, 'page_ready_state': 'complete', 'has_search_ui': True, 'playback_error_visible': False}
        code, result = call('/api/bridge/heartbeat', payload)
        assert code == 200, result
        assert call('/api/status')[1]['bridge']['extension_connected']
        assert call('/api/commands', {'type': 'FOLLOW', 'query': 'gadgets'})[0] == 422
        code, command = call('/api/commands', {'type': 'SEARCH', 'query': 'gadgets & home'})
        assert code == 201
        assert call('/api/bridge/commands/next?extension_id=wrong')[0] == 409
        assert call('/api/bridge/commands/next?extension_id=ext')[1]['command']['id'] == command['id']
        assert call('/api/bridge/commands/next?extension_id=ext')[1]['command'] is None
        assert call(f"/api/bridge/commands/{command['id']}/result", {'extension_id': 'ext', 'status': 'SUCCEEDED', 'detail': 'navigation accepted'})[0] == 200
        assert call('/api/commands')[1]['items'][0]['status'] == 'SUCCEEDED'
        assert any('SUCCEEDED' in e['message'] for e in call('/api/events')[1]['items'])
        for args in (('--loading',), ('--no-tab',)):
            code, result = call('/api/bridge/heartbeat', extension_heartbeat(*args))
            assert code == 200, result
        assert not call('/api/status')[1]['bridge']['tiktok_open']
        assert call('/api/bridge/heartbeat', {})[0] == 200
        assert call('/api/bridge/heartbeat', {'page_title': None, 'page_ready_state': None})[0] == 200
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
