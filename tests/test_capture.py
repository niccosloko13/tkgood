from scripts.process_runtime import hidden_kwargs
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
from app.extraction import DETAIL_VERSION


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
        result = json.loads(subprocess.check_output(['node', str(script), base, *args], text=True, timeout=20, **hidden_kwargs()))
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
    assert video['views'] == 1200000 and video['views_raw'] == '1.2M' and video['source'] == 'tiktok'
    assert video['search_query'] == 'home gadgets'
    assert video['shares'] is None and video['comments_count'] is None
    assert video['first_seen_at'] == video['last_seen_at'] == video['collected_at']
    assert video['video_id'] == '123456789' and video['search_position'] == 1
    code, quality = call('/api/extraction/quality')
    assert code == 200
    assert quality['total'] == 2
    assert quality['coverage'] == {'video_url': 100, 'video_id': 100, 'creator': 50, 'caption': 50, 'views': 50, 'thumbnail': 50}
    assert quality['extractor_version'] == 'tiktok-search-card-v2'
    assert not quality['thresholds_met']
    # Retried acknowledgement must not write observations or duplicate logs.
    event_count = len(call('/api/events')[1]['items'])
    assert call(f'/api/bridge/commands/{command_id}/result', payload)[0] == 200
    assert len(call('/api/events')[1]['items']) == event_count
    assert call('/api/videos/recent')[1] == recent
    mutated = json.loads(json.dumps(payload))
    mutated['capture']['results'][0]['raw_visible_text'] = 'changed evidence'
    assert call(f'/api/bridge/commands/{command_id}/result', mutated)[0] == 409
    capture('--update')
    assert call('/api/videos/count')[1]['total'] == 2
    latest = {v['video_url']: v for v in call('/api/videos/recent')[1]['items']}
    updated = latest[video['video_url']]
    assert updated['id'] == video['id']
    assert updated['first_seen_at'] == video['first_seen_at']
    assert updated['last_seen_at'] > video['last_seen_at']
    assert updated['views'] == 1300000
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


def test_enriched_eight_card_fixture_through_real_scripts_and_api(api):
    base, call = api
    call('/api/bridge/heartbeat', {'current_url': 'https://www.tiktok.com/search?q=home+gadgets'})
    call('/api/commands', {'type': 'READ_SEARCH_RESULTS'})
    script = Path(__file__).with_name('capture_client.cjs')
    response = json.loads(subprocess.check_output(['node', str(script), base, '--enrichment'], text=True, timeout=20, **hidden_kwargs()))
    assert response['http_status'] == 200
    assert response['body']['capture']['results_count'] == 8
    code, quality = call('/api/extraction/quality')
    assert code == 200 and quality['thresholds_met']
    assert quality['coverage'] == {'video_url': 100, 'video_id': 100, 'creator': 87.5, 'caption': 87.5, 'views': 87.5, 'thumbnail': 62.5}
    assert quality['complete'] == 6 and quality['partial'] == 2 and quality['minimal'] == 0
    videos = call('/api/videos/recent')[1]['items']
    alpha = next(v for v in videos if v['video_id'] == '1001')
    assert alpha['field_evidence']['views']['value'] == 83100
    assert alpha['field_evidence']['views']['raw_value'] == '83.1K'
    assert alpha['field_evidence']['views']['source'] == 'search_card'
    assert alpha['field_evidence']['views']['observed_at'] == alpha['collected_at']
    assert 'doNotStoreToken' not in alpha['card_snapshot']


def test_read_video_detail_api_is_known_video_only_and_preserves_capture_coverage(api):
    from app.schemas import VideoDetail
    from test_enrichment import result
    _, call = api
    call('/api/bridge/heartbeat', {'current_url':'https://www.tiktok.com/search?q=home+gadgets'})
    assert call('/api/commands', {'type':'READ_VIDEO_DETAIL','video_url':'https://www.tiktok.com/settings'})[0] == 422
    assert call('/api/commands', {'type':'READ_VIDEO_DETAIL','video_url':'https://www.tiktok.com/@maker/video/123'})[0] == 404
    capture_id = call('/api/commands', {'type':'READ_SEARCH_RESULTS'})[1]['id']
    call('/api/bridge/commands/next?extension_id=ext')
    search = capture_body()
    assert call(f'/api/bridge/commands/{capture_id}/result', {'extension_id':'ext','status':'SUCCEEDED','capture':search})[0] == 200
    quality_before = call('/api/extraction/quality')[1]
    command_id = call('/api/commands', {'type':'READ_VIDEO_DETAIL','video_url':'https://www.tiktok.com/@maker/video/123'})[1]['id']
    call('/api/bridge/commands/next?extension_id=ext')
    detail = result('https://www.tiktok.com/@maker/video/123',caption='Visible detail caption')
    detail.update(extraction_version=DETAIL_VERSION, search_position=None, likes='31.2K')
    for evidence in detail['field_evidence'].values():
        evidence['source']='video_detail'
    detail['field_evidence']['views']['method']='semantic_text'
    detail['field_evidence']['views']['confidence']=.98
    detail['field_evidence']['likes']={'value':31200,'raw_value':'31.2K','source':'video_detail','confidence':.98,'method':'semantic_text'}
    VideoDetail(**detail)
    body={'extension_id':'ext','status':'SUCCEEDED','video_detail':detail}
    assert call(f'/api/bridge/commands/{command_id}/result', body)[0] == 200
    assert call(f'/api/bridge/commands/{command_id}/result', body)[0] == 200
    assert call('/api/extraction/quality')[1] == quality_before
    video=call('/api/videos/recent')[1]['items'][0]
    assert video['caption']=='Visible detail caption'
    assert video['field_evidence']['caption']['source']=='video_detail'
    assert video['field_evidence']['likes']['value']==31200
    with db.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM video_detail_observations').fetchone()[0] == 1
        assert con.execute('SELECT COUNT(*) FROM search_observations').fetchone()[0] == 1


def test_detail_metrics_actual_js_payload_and_strict_provenance(api):
    import copy
    from app.schemas import VideoDetail, SearchResults
    from pydantic import ValidationError
    _, call = api
    call('/api/bridge/heartbeat', {'current_url':'https://www.tiktok.com/search?q=home+gadgets'})
    ident = call('/api/commands', {'type':'READ_SEARCH_RESULTS'})[1]['id']
    call('/api/bridge/commands/next?extension_id=ext')
    assert call(f'/api/bridge/commands/{ident}/result', {'extension_id':'ext','status':'SUCCEEDED','capture':capture_body()})[0] == 200
    quality = call('/api/extraction/quality')[1]
    payload = json.loads(subprocess.check_output(['node',str(Path(__file__).with_name('detail_payload.cjs'))],text=True,timeout=10, **hidden_kwargs()))
    VideoDetail(**payload)
    for metric in ('likes','comments_count','shares','favorites'):
        assert payload['field_evidence'][metric]['source']=='video_detail'
    legacy=copy.deepcopy(payload)
    legacy['extraction_version']='tiktok-video-detail-v1'
    for evidence in legacy['field_evidence'].values(): evidence.pop('method',None)
    VideoDetail(**legacy)
    for invalid in ('confidence','method','raw_value'):
        changed=copy.deepcopy(payload)
        changed['field_evidence']['likes'][invalid]={'confidence':1.0,'method':'guessed','raw_value':'Curtida 31.2K'}[invalid]
        with pytest.raises(ValidationError): VideoDetail(**changed)
    for version in ('tiktok-video-detail-v1','tiktok-video-detail-v2'):
        with pytest.raises(ValidationError):
            SearchResults(**{**capture_body(),'results':[{**payload,'extraction_version':version}]})
    command_id=call('/api/commands', {'type':'READ_VIDEO_DETAIL','video_url':payload['video_url']})[1]['id']
    call('/api/bridge/commands/next?extension_id=ext')
    body={'extension_id':'ext','status':'SUCCEEDED','video_detail':payload}
    assert call(f'/api/bridge/commands/{command_id}/result',body)[0] == 200
    assert call(f'/api/bridge/commands/{command_id}/result',body)[0] == 200
    video=call('/api/videos/recent')[1]['items'][0]
    assert video['field_evidence']['likes']['value']==31200
    assert video['field_evidence']['likes']['raw_value']=='31.2K'
    assert video['field_evidence']['likes']['method']=='aria_label'
    assert video['field_evidence']['comments_count']['value']==2251
    assert video['field_evidence']['shares']['value']==21400
    assert video['field_evidence']['favorites']['value']==1400000
    assert call('/api/extraction/quality')[1]==quality
