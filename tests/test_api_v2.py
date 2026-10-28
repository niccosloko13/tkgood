import json
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api_v2 import home_read_model
from app.api_v2_discovery import discovery_read_model
from app.api_v2_opportunities import opportunities_read_model
from app.api_v2_library import library_read_model
from app.api_v2_system import system_read_model
from app import api_v2_market_radar


def database():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript('''
      CREATE TABLE videos(id INTEGER PRIMARY KEY, video_id TEXT, canonical_url TEXT, creator_username TEXT,
        creator_display_name TEXT, caption TEXT, thumbnail_url TEXT, first_seen_at TEXT, last_seen_at TEXT);
      CREATE TABLE search_observations(id INTEGER PRIMARY KEY, video_id INTEGER, observed_at TEXT, search_query TEXT, fields_json TEXT);
      CREATE TABLE product_candidates(id INTEGER PRIMARY KEY, canonical_name TEXT, status TEXT, manual_status TEXT);
      CREATE TABLE top_opportunities(candidate_id INTEGER PRIMARY KEY, computed_at TEXT, result_json TEXT);
      CREATE TABLE viral_products_72h_missions(id TEXT PRIMARY KEY, status TEXT, updated_at TEXT, queries_json TEXT,
        results INTEGER, new_videos INTEGER, duplicates INTEGER);
    ''')
    return con


def test_market_radar_overview_is_read_only_and_uses_persisted_market_data(monkeypatch):
    class Store:
        def categories(self):
            return [{"id": "MLB432600", "label": "MLB432600", "last_observed_at": "2026-10-28T10:00:00+00:00"}]

        def top(self, *, category, limit):
            assert category == "MLB432600" and limit == 20
            return {"products": [{"external_id": "MLB1", "observed_at": "2026-10-28T10:00:00+00:00", "rank": 1}]}

        def trends(self, *, category):
            assert category == "MLB432600"
            return {"trends": [{"keyword": "tesoura", "position": 1}]}

    monkeypatch.setattr(api_v2_market_radar, "hosted_market_store", lambda: Store())
    monkeypatch.setattr(api_v2_market_radar, "mercado_livre_auth_config", lambda: SimpleNamespace(access_token="server-only"))
    result = api_v2_market_radar.market_radar_overview()
    assert result["default_category"] == "MLB432600"
    assert result["source_quality"] == "HIGH"
    assert len(result["products"]) == 1
    assert result["trends"][0]["keyword"] == "tesoura"
    assert result["sources"][0]["status"] == "OPERACIONAL"


def test_market_radar_overview_handles_unconfigured_storage_without_collecting(monkeypatch):
    monkeypatch.setattr(api_v2_market_radar, "hosted_market_store", lambda: None)
    monkeypatch.setattr(api_v2_market_radar, "mercado_livre_auth_config", lambda: SimpleNamespace(access_token=None))
    result = api_v2_market_radar.market_radar_overview()
    assert result["products"] == []
    assert result["trends"] == []
    assert result["sources"][0]["status"] == "AGUARDANDO_AUTORIZACAO"


def test_market_radar_category_tree_requires_control_and_returns_sanitized_categories(monkeypatch):
    class Client:
        def get(self, path):
            assert path == "/categories/MLB1"
            return {"id": "MLB1", "name": "Casa", "children_categories": [{"id": "MLB2", "name": "Folha"}]}

    monkeypatch.setattr(api_v2_market_radar, "_require_market_radar_control", lambda request: None)
    monkeypatch.setattr(api_v2_market_radar, "MercadoLivreAdapter", lambda: SimpleNamespace(client=Client()))
    result = api_v2_market_radar.mercado_livre_categories(SimpleNamespace(), "MLB1")
    assert result == {"parent": {"id": "MLB1", "name": "Casa", "is_leaf": False}, "categories": [{"id": "MLB2", "name": "Folha", "is_leaf": False}]}


def test_market_radar_diagnostic_is_bounded_and_never_reads_orders(monkeypatch):
    class Client:
        def get(self, path, params=None):
            if path == "/items/MLB123":
                return {"title": "Item", "thumbnail": "https://image.example/a.jpg", "permalink": "https://ml.example/a", "sold_quantity": 9}
            if path == "/items/MLB123/prices":
                return [{"amount": 19.9, "currency_id": "BRL"}]
            if path == "/items/MLB123/visits/time_window":
                assert params == {"last": "2", "unit": "day"}
                return {"total_visits": 42}
            raise AssertionError(path)

    monkeypatch.setattr(api_v2_market_radar, "_require_market_radar_control", lambda request: None)
    monkeypatch.setattr(api_v2_market_radar, "MercadoLivreAdapter", lambda: SimpleNamespace(client=Client()))
    request = api_v2_market_radar.MercadoLivreDiagnosticRequest(records=[
        {"external_id": "MLB123", "ranking_type": "ITEM"},
    ])
    result = api_v2_market_radar.diagnose_mercado_livre_records(request, SimpleNamespace())
    assert result["orders_checked"] is False and result["snapshots_written"] == 0
    assert result["records"] == [{"external_id": "MLB123", "ranking_type": "ITEM", "detail_status": "AVAILABLE",
        "price_status": "AVAILABLE", "visits_status": "AVAILABLE", "sold_quantity_status": "AVAILABLE",
        "title": "Item", "image_url": "https://image.example/a.jpg", "product_url": "https://ml.example/a",
        "sold_quantity": 9, "price": 19.9, "currency": "BRL", "visits": 42}]


def test_home_read_model_is_empty_and_read_only():
    con = database()
    before = con.total_changes
    result = home_read_model(con, datetime(2026, 10, 27, tzinfo=timezone.utc))
    assert result['summary'] == {'library_videos': 0, 'recently_detected': 0, 'identified_products': 0, 'strong_signals': 0}
    assert result['pulse'] == {'signal_count': 0, 'rising_count': 0, 'new_signal_count': 0}
    assert result['top_opportunities'] == []
    assert result['recent_discoveries'] == []
    assert result['last_mission'] is None
    assert con.total_changes == before


def test_home_read_model_maps_existing_data_and_limits_opportunities():
    con = database()
    now = '2026-10-27T00:00:00+00:00'
    con.execute('INSERT INTO videos VALUES (1,?,?,?,?,?,?,?,?)', ('123', 'https://www.tiktok.com/@one/video/123', 'one', None, 'A useful product', 'https://image.example/1.jpg', now, now))
    con.execute('INSERT INTO search_observations VALUES (1,1,?,?,?)', (now, 'home finds', json.dumps({'views': 31200, 'likes': 1200})))
    con.execute("INSERT INTO product_candidates VALUES (1,'Produto identificado','corroborated',NULL)")
    con.execute("INSERT INTO product_candidates VALUES (2,'Apenas observado','observed',NULL)")
    for candidate_id, lifecycle in enumerate(('EARLY_SIGNAL', 'EMERGING', 'ACCELERATING', 'DISCOVERED'), start=1):
        payload = {'candidate_id': candidate_id, 'display_name': f'Produto {candidate_id}', 'lifecycle': lifecycle,
                   'velocity_summary': 'RISING', 'saturation': 'LOW', 'observation_count': candidate_id,
                   'query_spread': 2, 'creator_spread': 1, 'why': [{'text': 'Apareceu em duas buscas.'}]}
        con.execute('INSERT INTO top_opportunities VALUES (?,?,?)', (candidate_id, now, json.dumps(payload)))
    con.execute('INSERT INTO viral_products_72h_missions VALUES (?,?,?,?,?,?,?)', ('mission', 'SUCCEEDED', now, json.dumps(['a', 'b']), 20, 5, 15))
    result = home_read_model(con, datetime(2026, 10, 27, 1, tzinfo=timezone.utc))
    assert result['summary'] == {'library_videos': 1, 'recently_detected': 1, 'identified_products': 1, 'strong_signals': 3}
    assert result['pulse'] == {'signal_count': 3, 'rising_count': 3, 'new_signal_count': 1}
    assert [item['lifecycle'] for item in result['top_opportunities']] == ['ACCELERATING', 'EMERGING', 'EARLY_SIGNAL']
    assert result['recent_discoveries'][0]['data_quality'] == 'COMPLETE'
    assert result['recent_discoveries'][0]['metrics'] == {'views': 31200, 'likes': 1200}
    assert result['last_mission']['queries'] == 2


def test_home_omits_thumbnail_only_discoveries():
    con = database()
    now = '2026-10-27T00:00:00+00:00'
    con.execute('INSERT INTO videos VALUES (1,?,?,?,?,?,?,?,?)', ('123', 'https://www.tiktok.com/@one/video/123', None, None, None, 'https://image.example/1.jpg', now, now))
    con.execute('INSERT INTO search_observations VALUES (1,1,?,?,?)', (now, 'home finds', '{}'))
    assert home_read_model(con)['recent_discoveries'] == []


def test_discovery_read_model_handles_idle_active_and_query_performance():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript('''
      CREATE TABLE search_captures(capture_id TEXT, search_query TEXT, observed_at TEXT, new_count INTEGER, updated_count INTEGER);
      CREATE TABLE safe_collection_batches(id TEXT PRIMARY KEY,stage INTEGER,status TEXT,created_at TEXT,validation_id TEXT,queries_json TEXT,query_index INTEGER,command_id INTEGER,new_videos INTEGER,seen INTEGER,duplicates INTEGER,snapshots INTEGER,stop_reason TEXT,completed_at TEXT);
      CREATE TABLE bridge_commands(id INTEGER PRIMARY KEY,options_json TEXT);
      CREATE TABLE safe_query_metrics(command_id INTEGER PRIMARY KEY,batch_id TEXT,query TEXT,status TEXT,results INTEGER,new_videos INTEGER,duplicates INTEGER,blocked INTEGER,invalid INTEGER,unique_creators INTEGER,category_matches INTEGER,observed_at TEXT,snapshots INTEGER);
      CREATE TABLE search_observations(id INTEGER PRIMARY KEY,video_id INTEGER,capture_id TEXT);
      CREATE TABLE trend_snapshot_sources(source_key TEXT);
      CREATE TABLE product_candidates(id INTEGER PRIMARY KEY);
      CREATE TABLE product_candidate_evidence(candidate_id INTEGER,video_id INTEGER);
    ''')
    bridge = {'connected': True, 'heartbeat_fresh': True, 'chrome_connected': True, 'tiktok_open': True,
              'tiktok_session_status': 'confirmed', 'current_page_status': 'healthy'}
    idle = discovery_read_model(con, bridge, {})
    assert idle['connection'] == {'ready': True, 'status': 'CONNECTED', 'label': 'Babi pronta para pesquisar'}
    assert idle['active_run'] is None
    con.execute("INSERT INTO safe_collection_batches VALUES ('batch',2,'PENDING','2026-10-27T00:00:00+00:00','check','[\"home gadgets\",\"kitchen gadgets\"]',1,7,3,8,5,0,NULL,NULL)")
    con.execute("INSERT INTO bridge_commands VALUES (7,'{\"safe_collection_id\": \"batch\"}')")
    con.execute("INSERT INTO search_captures VALUES ('one','home gadgets','2026-10-27T00:00:00+00:00',7,3)")
    active = discovery_read_model(con, bridge, {})
    assert active['active_run']['current_query'] == 'home gadgets'
    assert active['active_run']['queries_total'] == 2
    assert active['query_performance'][0]['novelty_rate'] == .7


def test_discovery_read_model_exposes_human_blocked_state():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    bridge = {'connected': True, 'heartbeat_fresh': True, 'chrome_connected': True, 'tiktok_open': True,
              'tiktok_session_status': 'unconfirmed', 'current_page_status': 'challenge'}
    result = discovery_read_model(con, bridge, {'reason': 'CAPTCHA'})
    assert result['connection'] == {'ready': False, 'status': 'BLOCKED', 'label': 'Ação necessária no TikTok'}


def test_opportunities_read_model_groups_persisted_engine_states_without_writing():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript('CREATE TABLE top_opportunities(candidate_id INTEGER PRIMARY KEY,result_json TEXT); CREATE TABLE trend_change_events(id INTEGER PRIMARY KEY,candidate_id INTEGER,event_type TEXT,observed_at TEXT);')
    states = [('EMERGING', 'MEDIUM', 'LOW'), ('EARLY_SIGNAL', 'LOW', 'LOW'), ('SATURATED', 'MEDIUM', 'HIGH')]
    for candidate_id, (lifecycle, quality, saturation) in enumerate(states, 1):
        con.execute('INSERT INTO top_opportunities VALUES (?,?)', (candidate_id, json.dumps({'candidate_id': candidate_id, 'display_name': 'Soap dispenser' if candidate_id == 1 else f'Produto {candidate_id}', 'lifecycle': lifecycle, 'velocity_summary': 'RISING', 'saturation': saturation, 'observation_count': 8, 'query_spread': 2, 'creator_spread': 2, 'evidence_quality': quality, 'why': [{'text': 'Apareceu em buscas diferentes.'}], 'risks': [], 'insufficient_signals': [], 'observation_ids': ['search_observations:1']})))
    before = con.total_changes
    result = opportunities_read_model(con)
    assert result['summary'] == {'total': 3, 'strong': 1, 'watching': 1, 'saturated': 1}
    assert result['top'][0]['display_name'] == 'Dispenser de sabão'
    assert result['watchlist'][0]['state']['label'] == 'Sinal inicial'
    assert result['saturated'][0]['state']['saturation'] == 'Alta'
    assert con.total_changes == before


def test_library_read_model_is_paginated_read_only_and_handles_empty_database():
    con = database()
    before = con.total_changes
    result = library_read_model(con, page=1, page_size=20)
    assert result == {"page": 1, "page_size": 20, "total": 0, "items": [], "filters": {"queries": [], "creators": []}}
    assert con.total_changes == before


def test_library_read_model_filters_sorts_and_exposes_related_product():
    con = database()
    con.execute('CREATE TABLE product_candidate_evidence(id INTEGER PRIMARY KEY,candidate_id INTEGER,video_id INTEGER,observed_at TEXT)')
    now = '2026-10-27T12:00:00+00:00'
    old = '2026-10-26T12:00:00+00:00'
    con.execute("INSERT INTO product_candidates VALUES (1,'Soap dispenser','corroborated',NULL)")
    con.execute('INSERT INTO videos VALUES (1,?,?,?,?,?,?,?,?)', ('one', 'https://www.tiktok.com/@ana/video/one', 'ana', None, 'Soap dispenser for kitchen', 'https://img/1', old, now))
    con.execute('INSERT INTO videos VALUES (2,?,?,?,?,?,?,?,?)', ('two', 'https://www.tiktok.com/@bia/video/two', 'bia', None, 'Brush for dishes', None, now, now))
    con.execute('INSERT INTO videos VALUES (3,?,?,?,?,?,?,?,?)', ('three', 'https://www.tiktok.com/@ana/video/three', 'ana', None, None, None, '2026-10-25T12:00:00+00:00', '2026-10-25T12:00:00+00:00'))
    con.execute('INSERT INTO search_observations VALUES (1,1,?,?,?)', (now, 'kitchen finds', json.dumps({'views': 83700, 'likes': 1200})))
    con.execute('INSERT INTO search_observations VALUES (2,2,?,?,?)', (now, 'home finds', json.dumps({'comments_count': 1327})))
    con.execute('INSERT INTO search_observations VALUES (3,3,?,?,?)', ('2026-10-25T12:00:00+00:00', 'home finds', '{}'))
    con.execute('UPDATE videos SET canonical_url=NULL, creator_username=NULL WHERE id=3')
    con.execute('INSERT INTO product_candidate_evidence VALUES (1,1,1,?)', (now,))
    before = con.total_changes
    page = library_read_model(con, page=1, page_size=1, sort='views')
    assert page['total'] == 3
    assert page['items'][0]['video_id'] == 'one'
    assert page['items'][0]['product']['id'] == '1'
    assert page['items'][0]['product']['name'].startswith('Dispenser')
    assert page['items'][0]['data_quality'] == 'COMPLETE'
    assert library_read_model(con, text='brush')['items'][0]['video_id'] == 'two'
    assert library_read_model(con, quality='MINIMAL')['items'][0]['video_id'] == 'three'
    assert library_read_model(con, identified=True)['total'] == 1
    assert library_read_model(con, query='home finds')['total'] == 2
    assert library_read_model(con, creator='ana')['total'] == 1
    assert library_read_model(con, candidate_id='1')['total'] == 1
    assert library_read_model(con, sort='oldest')['items'][0]['video_id'] == 'three'
    assert con.total_changes == before


def test_system_read_model_is_human_read_only_and_reports_quality():
    con = database()
    con.execute('CREATE TABLE events(id INTEGER PRIMARY KEY,created_at TEXT,level TEXT,event_type TEXT,message TEXT)')
    now = '2026-10-27T12:00:00+00:00'
    con.execute('INSERT INTO videos VALUES (1,?,?,?,?,?,?,?,?)', ('one', 'https://www.tiktok.com/@ana/video/one', 'ana', None, 'Useful item', 'https://img/1', now, now))
    con.execute('INSERT INTO search_observations VALUES (1,1,?,?,?)', (now, 'home finds', json.dumps({'views': 31200, 'likes': 1200})))
    con.execute("INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)", (now, 'INFO', 'session', 'raw technical details must not reach the normal event copy'))
    bridge = {'connected': True, 'heartbeat_fresh': True, 'chrome_connected': True, 'tiktok_open': True,
              'tiktok_session_status': 'confirmed', 'current_page_status': 'healthy', 'current_url': 'https://www.tiktok.com/', 'build_id': 'build'}
    before = con.total_changes
    result = system_read_model(con, bridge, {})
    assert result['overall'] == {'status': 'HEALTHY', 'label': 'Tudo funcionando normalmente'}
    assert result['browser']['label'] == 'Conectado'
    assert result['session']['label'] == 'Confirmada'
    assert result['security']['label'] == 'Nenhum bloqueio ativo'
    assert result['data_quality'] == {'videos': 1, 'complete': 1, 'partial': 0, 'minimal': 0}
    assert result['direct_video_enrichment']['label'] == 'Disponível'
    assert result['events'][0]['label'] == 'Sessão do TikTok atualizada'
    assert 'raw technical' not in str(result['events'])
    assert con.total_changes == before


def test_system_read_model_maps_disconnected_login_and_blocked_without_recovery():
    con = database()
    offline = system_read_model(con, {'connected': False, 'heartbeat_fresh': False}, {})
    login = system_read_model(con, {'connected': True, 'heartbeat_fresh': True, 'chrome_connected': True, 'tiktok_open': True,
                                    'tiktok_session_status': 'login_required', 'current_page_status': 'healthy'}, {})
    blocked = system_read_model(con, {'connected': True, 'heartbeat_fresh': True, 'chrome_connected': True, 'tiktok_open': True,
                                      'tiktok_session_status': 'confirmed', 'current_page_status': 'challenge'}, {'reason': 'CAPTCHA'})
    assert offline['browser']['label'] == 'Indisponível'
    assert login['session']['label'] == 'Login necessário'
    assert blocked['overall']['status'] == 'ATTENTION'
    assert blocked['security']['label'] == 'Ação necessária no TikTok'
