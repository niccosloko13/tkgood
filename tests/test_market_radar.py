import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

from app.market_radar.capabilities import as_dict, default_capabilities, source_confidence
from app.market_radar.models import Category, Marketplace, MarketplaceProductObservation, Movement, NormalizedProduct, SourceConfidence, SourceType
from app.market_radar.normalization import normalize_currency, normalize_number, normalize_text, normalize_url, normalized_title
from app.market_radar.ranking import movement
from app.market_radar.repository import history, migrate, save_observation
from app.market_radar.adapters.mercado_livre import (MercadoLivreAdapter, MercadoLivreAuthError,
                                                      MercadoLivreCategoryNotRanked, MercadoLivreClient)
from app.market_radar.adapters.aliexpress import AliExpressAffiliateAdapter, AliExpressAdapterError
from app.market_radar.repository import search_trends
from app.market_radar.service import get_top_products, run_marketplace_collection, sources_read_model
from app.market_radar import mercado_livre_auth as oauth


def test_postgres_store_keeps_category_on_each_snapshot_not_on_mutable_product():
    """Regression: one external product may rank in more than one category."""
    source = Path("app/market_radar/postgres_store.py").read_text(encoding="utf-8")
    assert "source_category TEXT" in source
    assert "INSERT INTO market_radar_snapshots(product_id,observed_at,source_category" in source
    assert "AND s.source_category=%s" in source
    assert "DISTINCT ON (p.id,s.source_category)" in source
    assert "ON CONFLICT(marketplace,external_id) DO UPDATE SET title=EXCLUDED.title,normalized_title=EXCLUDED.normalized_title,image_url" in source


def test_postgres_store_backfills_legacy_snapshot_categories_from_official_evidence():
    source = Path("app/market_radar/postgres_store.py").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS source_category TEXT" in source
    assert "evidence_json->>'source_category_id'" in source
    assert "market_radar_snapshot_category_time_idx" in source


def database():
    con = sqlite3.connect(':memory:'); con.row_factory = sqlite3.Row; migrate(con); return con


def observation(external_id='a', at='2026-10-27T12:00:00+00:00', rank=18, **values):
    product = NormalizedProduct(Marketplace.MERCADO_LIVRE, external_id, values.pop('title', '  Escova\u00a0Elétrica  '), normalized_title('  Escova\u00a0Elétrica  ') or '', category=values.pop('category', Category.LIMPEZA), product_url=values.pop('product_url', 'https://example.test/product?a=1#fragment'))
    return MarketplaceProductObservation(product, at, rank=rank, source_type=values.pop('source_type', SourceType.OFFICIAL_RANKING), source_confidence=values.pop('source_confidence', SourceConfidence.HIGH), **values)


def test_models_capabilities_and_normalization_are_explicit():
    assert normalize_text('  A\u00a0 B  ') == 'A B'
    assert normalized_title('Água  Quente') == 'água quente'
    assert normalize_currency(' brl ') == 'BRL'
    assert normalize_number('1.234,50') == 1234.5
    assert normalize_url('https://EXAMPLE.test/x?a=1#fragment') == 'https://example.test/x?a=1'
    assert as_dict(default_capabilities())['supports_rank'] is False
    assert source_confidence(SourceType.OFFICIAL_API) == SourceConfidence.HIGH


def test_snapshot_persistence_dedupes_identity_and_preserves_missing_metrics():
    con = database()
    save_observation(con, observation(rank=5, price=12.5, currency='BRL'))
    save_observation(con, observation(at='2026-10-28T12:00:00+00:00', rank=3, views=200))
    assert con.execute('SELECT count(*) FROM market_products').fetchone()[0] == 1
    assert con.execute('SELECT count(*) FROM market_snapshots').fetchone()[0] == 2
    row = con.execute('SELECT sales_count,order_count,views FROM market_snapshots ORDER BY id DESC LIMIT 1').fetchone()
    assert tuple(row) == (None, None, 200)


def test_history_windows_and_available_from_do_not_invent_prior_history():
    con = database(); base = datetime(2026, 10, 27, tzinfo=timezone.utc)
    for days in (0, 2, 6, 29, 89):
        save_observation(con, observation(at=(base - timedelta(days=days)).isoformat(), rank=10-days))
    assert len(history(con, marketplace='MERCADO_LIVRE', since=(base-timedelta(days=1)).isoformat())) == 1
    assert len(history(con, marketplace='MERCADO_LIVRE', since=(base-timedelta(days=3)).isoformat())) == 2
    assert len(history(con, marketplace='MERCADO_LIVRE', since=(base-timedelta(days=7)).isoformat())) == 3
    assert len(history(con, marketplace='MERCADO_LIVRE', since=(base-timedelta(days=30)).isoformat())) == 4
    result = get_top_products(con, marketplace=Marketplace.MERCADO_LIVRE)
    assert result['history_available_from'] == (base-timedelta(days=89)).isoformat()


def test_movement_is_explainable_and_top_twenty_is_source_rank_limited():
    assert movement(12, 18) == (Movement.UP, 6)
    assert movement(8, 5) == (Movement.DOWN, -3)
    assert movement(17, None) == (Movement.NEW_ENTRY, None)
    assert movement(3, 3) == (Movement.STABLE, 0)
    con = database()
    for rank in range(25, 0, -1):
        save_observation(con, observation(external_id=str(rank), rank=rank))
    products = get_top_products(con, marketplace=Marketplace.MERCADO_LIVRE, limit=99)['products']
    assert len(products) == 20
    assert products[0]['current_rank'] == 1
    assert products[-1]['current_rank'] == 20
    assert products[0]['movement'] == 'NEW_ENTRY'


def test_top_products_compares_the_previous_snapshot_for_the_same_product():
    con = database()
    save_observation(con, observation(at='2026-10-26T12:00:00+00:00', rank=18))
    save_observation(con, observation(at='2026-10-27T12:00:00+00:00', rank=12))
    item = get_top_products(con, marketplace=Marketplace.MERCADO_LIVRE)['products'][0]
    assert item['previous_rank'] == 18
    assert item['rank_change'] == 6
    assert item['movement'] == 'UP'


def test_unavailable_adapters_are_isolated_and_do_not_simulate_products():
    con = database()
    result = run_marketplace_collection(con, marketplace=Marketplace.MERCADO_LIVRE)
    assert result == {'id': result['id'], 'status': 'UNAVAILABLE', 'received_count': 0, 'error': 'adapter unavailable'}
    sources = {entry['marketplace']: entry for entry in sources_read_model(con)}
    assert sources['MERCADO_LIVRE']['status'] == 'NOT_CONFIGURED'
    assert sources['MERCADO_LIVRE']['source_confidence'] == 'HIGH'
    assert sources['SHOPEE']['status'] == 'NOT_CONFIGURED'
    assert con.execute('SELECT count(*) FROM market_products').fetchone()[0] == 0
    assert con.execute("SELECT status,error_message FROM market_runs").fetchone()['status'] == 'UNAVAILABLE'


def _official_transport(highlights=None, item_rows=None, products=None, trends=None, categories=None):
    def request(url, headers):
        assert headers['Authorization'].startswith('Bearer ')
        if '/highlights/' in url:
            return highlights
        if '/categories/' in url:
            ident = url.rsplit('/', 1)[-1]
            return (categories or {}).get(ident, {'id': ident, 'name': 'Folha', 'children_categories': []})
        if '/items/bulk?' in url:
            return item_rows
        if '/products/' in url or '/user-products/' in url:
            ident = url.rsplit('/', 1)[-1]
            return (products or {}).get(ident)
        if '/trends/' in url:
            return trends
        raise AssertionError(url)
    return request


def test_official_adapter_resolves_item_product_and_user_product_with_partial_details():
    highlights = {'content': [
        {'id': 'MLB1', 'position': 1, 'type': 'ITEM'},
        {'id': 'MLB2', 'position': 2, 'type': 'PRODUCT'},
        {'id': 'MLBU3', 'position': 3, 'type': 'USER_PRODUCT'},
    ]}
    adapter = MercadoLivreAdapter(MercadoLivreClient('secret', _official_transport(
        highlights, [{'status_code': 200, 'body': {'id': 'MLB1', 'title': 'Item', 'price': 10, 'currency_id': 'BRL', 'permalink': 'https://ml/item'}}],
        {'MLB2': {'id': 'MLB2', 'title': 'Produto', 'price': 20, 'currency_id': 'BRL'}, 'MLBU3': None})))
    observations = adapter.fetch_top_products(category='MLB123', limit=99)
    assert len(observations) == 3
    assert [value.rank for value in observations] == [1, 2, 3]
    assert observations[0].product.title == 'Item'
    assert observations[1].product.title == 'Produto'
    assert observations[2].evidence['detail_resolved'] is False
    assert adapter.capabilities().supports_sales_count is False


def test_official_adapter_maps_category_404_and_auth_without_leaking_token():
    adapter = MercadoLivreAdapter(MercadoLivreClient(None))
    try:
        adapter.fetch_top_products(category='MLB123')
    except MercadoLivreAuthError as exc:
        assert 'token' in str(exc).lower()
        assert 'secret' not in str(exc)
    else:
        assert False


def test_non_leaf_category_is_not_used_to_invent_a_top_twenty():
    adapter = MercadoLivreAdapter(MercadoLivreClient('secret', _official_transport(categories={
        'MLB123': {'id': 'MLB123', 'name': 'Raiz', 'children_categories': [{'id': 'MLB456'}]},
    })))
    try:
        adapter.fetch_top_products(category='MLB123')
    except MercadoLivreCategoryNotRanked as exc:
        assert exc.code == 'CATEGORY_NOT_RANKED'
    else:
        assert False


def test_aliexpress_fixture_adapter_maps_official_affiliate_products_without_claiming_rank_or_sales():
    fixture = {"aliexpress_affiliate_hotproduct_query_response": {"resp_result": {"result": {"products": {"product": [
        {"product_id": "100", "product_title": "  Escova  ElÃ©trica ", "product_main_image_url": "https://img.example/100.jpg",
         "target_sale_price": "12.50", "target_sale_price_currency": "usd", "product_detail_url": "https://www.aliexpress.com/item/100.html",
         "second_level_category_name": "Home"},
        {"product_id": "101"},
    ]}}}}}
    calls = []
    adapter = AliExpressAffiliateAdapter(lambda **kwargs: calls.append(kwargs) or fixture)
    rows = adapter.fetch_top_products(category="casa", limit=99)
    assert calls == [{"method": "get_hotproducts", "category": "casa", "limit": 20}]
    assert len(rows) == 1
    assert rows[0].product.marketplace == Marketplace.ALIEXPRESS
    assert rows[0].product.title == "Escova ElÃ©trica"
    assert rows[0].price == 12.5 and rows[0].currency == "USD"
    assert rows[0].rank is None and rows[0].sales_count is None
    assert rows[0].evidence["collection_kind"] == "AFFILIATE_HOTPRODUCTS"
    assert rows[0].evidence["ranking_available"] is False
    assert adapter.capabilities().supports_rank is False


def test_aliexpress_fixture_adapter_stays_unavailable_without_approved_transport():
    adapter = AliExpressAffiliateAdapter()
    assert adapter.available is False
    try:
        adapter.fetch_top_products(category="casa")
    except AliExpressAdapterError as exc:
        assert "not configured" in str(exc)
    else:
        assert False


def test_trends_are_weekly_and_keep_10_20_20_types_separate():
    source = [{'keyword': f'produto {index}', 'url': f'https://ml/{index}'} for index in range(50)]
    adapter = MercadoLivreAdapter(MercadoLivreClient('secret', _official_transport(trends=source)))
    values = adapter.fetch_trends()
    assert len(values) == 50
    assert [item['trend_type'] for item in values[:10]] == ['FASTEST_GROWING'] * 10
    assert [item['trend_type'] for item in values[10:30]] == ['MOST_WANTED'] * 20
    assert [item['trend_type'] for item in values[30:]] == ['POPULAR_TREND'] * 20
    assert all(item['source_window'] == 'weekly' for item in values)
    con = database(); from app.market_radar.repository import save_search_trends
    save_search_trends(con, values)
    assert len(search_trends(con, marketplace='MERCADO_LIVRE')) == 50


def test_oauth_requires_config_and_keeps_state_and_tokens_out_of_the_response(monkeypatch, tmp_path):
    for key in ('MERCADO_LIVRE_CLIENT_ID', 'MERCADO_LIVRE_CLIENT_SECRET', 'MERCADO_LIVRE_REDIRECT_URI', 'MERCADO_LIVRE_ACCESS_TOKEN', 'MERCADO_LIVRE_REFRESH_TOKEN'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    try:
        oauth.start_authorization()
    except oauth.MercadoLivreOAuthError:
        pass
    else:
        assert False
    monkeypatch.setenv('MERCADO_LIVRE_CLIENT_ID', 'client')
    monkeypatch.setenv('MERCADO_LIVRE_CLIENT_SECRET', 'secret')
    monkeypatch.setenv('MERCADO_LIVRE_REDIRECT_URI', 'http://localhost/callback')
    start = oauth.start_authorization()
    assert 'state=' in start['authorization_url'] and 'client_secret' not in start['authorization_url']
    assert 'secret' not in start['authorization_url']


def test_oauth_refresh_posts_form_and_persists_tokens_only_to_ignored_local_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('MERCADO_LIVRE_CLIENT_ID', 'client')
    monkeypatch.setenv('MERCADO_LIVRE_CLIENT_SECRET', 'secret')
    monkeypatch.setenv('MERCADO_LIVRE_REDIRECT_URI', 'http://localhost/callback')
    monkeypatch.setenv('MERCADO_LIVRE_REFRESH_TOKEN', 'old-refresh')
    monkeypatch.setattr(oauth, '_post_form', lambda body: {'access_token': 'new-access', 'refresh_token': 'new-refresh', 'expires_in': 21600})
    result = oauth.refresh_mercado_livre_token()
    assert result['expires_in'] == 21600
    saved = (tmp_path / '.env').read_text(encoding='utf-8')
    assert 'new-access' in saved and 'new-refresh' in saved
    assert 'new-access' not in result and 'new-refresh' not in result
