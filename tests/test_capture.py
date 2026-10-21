import json
import socket
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
import uvicorn
from pydantic import ValidationError

from app import db
from app.main import app
from app.policy import ReadOnlyPolicy
from app.schemas import SearchResults, VisibleVideo


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'capture.db')
    db.init_db()


@pytest.fixture
def api(database):
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    base = f'http://127.0.0.1:{sock.getsockname()[1]}'
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()

    def call(path, body=None):
        request = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                          headers={'Content-Type': 'application/json', 'X-Extension-ID': 'ext'})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, json.load(exc)

    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        yield base, call
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()


def test_capture_policy():
    assert ReadOnlyPolicy().check('READ_SEARCH_RESULTS').allowed
    assert not ReadOnlyPolicy().check('LIKE').allowed
    assert not ReadOnlyPolicy().check('FOLLOW').allowed


def capture_body(**changes):
    return {'query': 'home gadgets', 'page_url': 'https://www.tiktok.com/search?q=home+gadgets',
            'results_count': 1, 'links_detected': 1,
            'results': [{'video_url': 'https://www.tiktok.com/@maker/video/123'}], **changes}


def test_capture_schema_nulls_and_strict_validation():
    result = SearchResults(**capture_body())
    assert result.results[0].creator_username is None
    assert result.results[0].views is None
    for changes in ({'query': 'different'}, {'results_count': 2}, {'links_detected': 0}, {'results_count': '1'},
                    {'page_url': 'https://evil.example/search?q=home+gadgets'},
                    {'results': [{'video_url': 'https://evil.example/@maker/video/123'}]},
                    {'results': [{'video_url': 'https://www.tiktok.com/@maker/video/123', 'likes': 12}]},
                    {'results': [{'video_url': 'https://www.tiktok.com/@maker/video/123', 'unknown': 'x'}]}):
        with pytest.raises(ValidationError):
            SearchResults(**capture_body(**changes))
    with pytest.raises(ValidationError):
        SearchResults(**capture_body(results_count=2, links_detected=2, results=[
            {'video_url': 'https://www.tiktok.com/@maker/video/123'},
            {'video_url': 'https://www.tiktok.com/@maker/video/123?tracking=x'}]))
    assert VisibleVideo(video_url='https://tiktok.com/@maker/video/123?tracking=x').video_url == 'https://www.tiktok.com/@maker/video/123'


def test_legacy_command_migration_preserves_search(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'legacy.db')
    with db.connect() as con:
        con.execute("""CREATE TABLE bridge_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type='SEARCH'), query TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('PENDING','DISPATCHED','SUCCEEDED','FAILED','EXPIRED')),
            extension_id TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '')""")
        con.execute("INSERT INTO bridge_commands VALUES (42,'2026-01-01','2026-01-01','SEARCH','old query','SUCCEEDED','ext','done')")
    db.init_db()
    db.init_db()
    with db.connect() as con:
        assert dict(con.execute('SELECT * FROM bridge_commands WHERE id=42').fetchone())['detail'] == 'done'
        assert con.execute('SELECT COUNT(*) FROM bridge_commands').fetchone()[0] == 1
    assert db.enqueue_command('READ_SEARCH_RESULTS', 'test', 'ext') > 42
    with pytest.raises(sqlite3.IntegrityError):
        db.enqueue_command('LIKE', 'test', 'ext')


def test_real_extension_capture_insert_update_counter_recent_and_logs(api):
    base, call = api
    assert call('/api/videos/count') == (200, {'total': 0})
    assert call('/api/commands', {'type': 'READ_SEARCH_RESULTS'})[0] == 409
    assert call('/api/bridge/heartbeat', {'extension_version': '0.1.4', 'current_url': 'https://www.tiktok.com/search?q=home+gadgets'})[0] == 200
    for forbidden in ('LIKE', 'FOLLOW', 'CLICK'):
        assert call('/api/commands', {'type': forbidden})[0] == 422

    def capture(*args):
        code, command = call('/api/commands', {'type': 'READ_SEARCH_RESULTS'})
        assert code == 201
        script = Path(__file__).with_name('capture_client.cjs')
        result = json.loads(subprocess.check_output(['node', str(script), base, *args], text=True, timeout=20))
        assert result['http_status'] == 200, result
        assert result['body']['status'] == 'SUCCEEDED'
        assert result['body']['capture']['results_count'] == 2
        return command['id'], result['body']

    command_id, payload = capture()
    assert call('/api/videos/count') == (200, {'total': 2})
    code, recent = call('/api/videos/recent')
    assert code == 200 and recent['total'] == 2
    first = {v['video_url']: v for v in recent['items']}
    video = first['https://www.tiktok.com/@maker/video/123456789']
    assert video['views'] == '1.2M' and video['source'] == 'tiktok'
    assert video['search_query'] == 'home gadgets'
    assert video['shares'] is None and video['comments_count'] is None
    assert video['first_seen_at'] == video['last_seen_at'] == video['collected_at']
    # Retried acknowledgement must not write observations or duplicate logs.
    event_count = len(call('/api/events')[1]['items'])
    assert call(f'/api/bridge/commands/{command_id}/result', payload)[0] == 200
    assert len(call('/api/events')[1]['items']) == event_count
    assert call('/api/videos/recent')[1] == recent
    mutated = json.loads(json.dumps(payload))
    mutated['capture']['results'][0]['views'] = '999'
    assert call(f'/api/bridge/commands/{command_id}/result', mutated)[0] == 409
    capture('--update')
    assert call('/api/videos/count')[1]['total'] == 2
    latest = {v['video_url']: v for v in call('/api/videos/recent')[1]['items']}
    updated = latest[video['video_url']]
    assert updated['id'] == video['id']
    assert updated['first_seen_at'] == video['first_seen_at']
    assert updated['last_seen_at'] > video['last_seen_at']
    assert updated['views'] == '1.3M'
    messages = [e['message'] for e in call('/api/events')[1]['items']]
    for expected in ('Capture requested', 'Reading visible search results', '3 result links detected',
                     '2 unique observations stored', '2 duplicates updated', 'Capture completed'):
        assert any(expected in m for m in messages), expected


def test_capture_result_requires_claim_owner_query_and_payload(api):
    _, call = api
    call('/api/bridge/heartbeat', {'current_url': 'https://www.tiktok.com/search?q=home+gadgets'})
    command_id = call('/api/commands', {'type': 'READ_SEARCH_RESULTS'})[1]['id']
    body = {'extension_id': 'ext', 'status': 'SUCCEEDED', 'capture': capture_body()}
    assert call(f'/api/bridge/commands/{command_id}/result', body)[0] == 409
    call('/api/bridge/commands/next?extension_id=ext')
    assert call(f'/api/bridge/commands/{command_id}/result', {**body, 'extension_id': 'other'})[0] == 404
    assert call(f'/api/bridge/commands/{command_id}/result', {'extension_id': 'ext', 'status': 'SUCCEEDED'})[0] == 409
    wrong = capture_body(query='other', page_url='https://www.tiktok.com/search?q=other')
    assert call(f'/api/bridge/commands/{command_id}/result', {**body, 'capture': wrong})[0] == 409
    assert call('/api/videos/count')[1]['total'] == 0
    assert call(f'/api/bridge/commands/{command_id}/result', body)[0] == 200
    assert call('/api/videos/count')[1]['total'] == 1
