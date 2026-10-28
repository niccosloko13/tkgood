from datetime import datetime, timedelta, timezone
import hmac
import os
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from . import db
from .market_radar.models import Marketplace
from .market_radar.scheduler import schedule
from .market_radar.service import get_market_trends, get_top_products, run_marketplace_collection, sources_read_model
from .market_radar.adapters.mercado_livre import MercadoLivreAdapter, MercadoLivreError
from .market_radar.postgres_store import hosted_market_store
from .market_radar.mercado_livre_auth import (MercadoLivreOAuthError, config as mercado_livre_auth_config,
                                               exchange_code, refresh_mercado_livre_token, start_authorization,
                                               storage_mode, authorization_grants_summary)


router = APIRouter(prefix="/api/v2/market-radar")


@router.get("/overview")
def market_radar_overview():
    """Small product-facing read model; it never initiates a collection."""
    store = hosted_market_store()
    auth = mercado_livre_auth_config()
    if store:
        categories = store.categories()
        default_category = categories[0]["id"] if categories else None
        top = store.top(category=default_category, limit=20)
        trends = store.trends(category=default_category)
        last_updated = max((item.get("observed_at") for item in top.get("products", [])), default=None)
    else:
        categories, default_category, top, trends, last_updated = [], None, {"products": []}, {"trends": []}, None
    sources = [
        {"id": "MERCADO_LIVRE", "label": "Mercado Livre", "status": "OPERACIONAL" if auth.access_token else "AGUARDANDO_AUTORIZACAO",
         "quality": "Fonte oficial", "description": "Rankings e tendências oficiais", "last_updated_at": last_updated},
        {"id": "ALIEXPRESS", "label": "AliExpress", "status": "EM_PREPARACAO",
         "quality": "Adapter de fixtures", "description": "Aguardando credenciais da API oficial", "last_updated_at": None},
        {"id": "SHOPEE", "label": "Shopee", "status": "INDISPONIVEL",
         "quality": "Sem fonte geral", "description": "Nenhuma fonte de ranking configurada", "last_updated_at": None},
        {"id": "ALIBABA", "label": "Alibaba", "status": "EM_PREPARACAO",
         "quality": "Em preparação", "description": "Fonte ainda não configurada", "last_updated_at": None},
        {"id": "SHEIN", "label": "SHEIN", "status": "INDISPONIVEL",
         "quality": "Sem fonte", "description": "Nenhuma fonte configurada", "last_updated_at": None},
    ]
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": sources,
            "categories": categories, "default_category": default_category,
            "last_updated_at": last_updated, "source_quality": "HIGH" if top.get("products") else None,
            "products": top.get("products", []), "trends": trends.get("trends", [])}


def _require_market_radar_control(request: Request) -> None:
    """Keep OAuth initiation, refresh and collection off the public surface."""
    if not os.environ.get("VERCEL"):
        return
    expected = os.environ.get("BABI_MARKET_RADAR_CONTROL_TOKEN")
    supplied = request.headers.get("X-Babi-Market-Radar-Control")
    if not expected:
        raise HTTPException(503, "Market Radar control is not configured")
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "Market Radar operator authorization is required")


@router.get("")
def market_radar(marketplace: Marketplace | None = None, category: str | None = None, limit: int = Query(20, ge=1, le=20)):
    with db.connect() as con:
        sources = sources_read_model(con)
        selected = get_top_products(con, marketplace=marketplace, category=category, limit=limit) if marketplace else None
        return {"mode": schedule().mode, "sources": sources, "top_products": selected}


@router.get("/offline-imports/{marketplace}")
def offline_marketplace_products(marketplace: Literal["SHOPEE", "ALIEXPRESS"]):
    """Read offline imports only. Never mix with official rankings."""
    from .market_radar.offline_store import MarketImportStore
    store = hosted_market_store()
    if store is None:
        return {"marketplace": marketplace, "mode": "OFFLINE_IMPORT", "products": [],
                "official_ranking": False, "count": 0}
    return MarketImportStore(store.database_url).latest(marketplace=marketplace, limit=20)


@router.get("/sources")
def market_radar_sources():
    with db.connect() as con:
        return sources_read_model(con)


_PERIODS = {"1d": 1, "3d": 3, "7d": 7, "15d": 15, "30d": 30, "60d": 60, "90d": 90}


def _with_period(payload: dict, period: str) -> dict:
    available = payload.get("history_available_from")
    if not available:
        payload["requested_window"] = period
        payload["history_complete"] = False
        return payload
    try:
        first = datetime.fromisoformat(available)
    except (TypeError, ValueError):
        payload["requested_window"] = period; payload["history_complete"] = False; return payload
    cutoff = datetime.now(timezone.utc) - timedelta(days=_PERIODS[period])
    payload["requested_window"] = period
    payload["history_complete"] = first <= cutoff
    return payload



@router.get("/commercial-ranking")
def commercial_ranking(
    marketplace: Literal["SHOPEE","ALIEXPRESS","MERCADO_LIVRE","TIKTOK_SHOP"] = "SHOPEE",
    metric: Literal["sold_30d","estimated_sold_30d","historical_sold","views_total","revenue_30d"] = "sold_30d",
    limit: int = Query(20, ge=1, le=50),
):
    """Verified provider-origin metrics, isolated from official ML bestseller ranking."""
    from .market_radar.commercial_metrics import hosted_commercial_store
    store=hosted_commercial_store()
    if not store:
        return {"marketplace":marketplace,"metric":metric,"products":[],"total":0,
                "observed_not_live":True,"note":"Neon commercial metrics not configured"}
    return store.ranking(marketplace=marketplace,metric=metric,limit=limit)


@router.get("/sales-window")
def market_sales_window(
    marketplace: Literal["MERCADO_LIVRE"] = "MERCADO_LIVRE",
    category: str | None = None,
    hours: Literal[48, 168, 720] = 48,
    sort: Literal["ranking", "recent", "price_low", "price_high", "rising"] = "ranking",
    top: int | None = Query(None, ge=1, le=20),
):
    """Official best-seller observations; NOT measured sales or visit counts."""
    from .market_radar.observation_windows import build_window
    store = hosted_market_store()
    if not store:
        return {**build_window([], hours, sort=sort, min_rank=top),
                "marketplace": marketplace, "category": category, "data_source": "NO_HOSTED_DATA"}
    from psycopg.rows import dict_row
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    params = [cutoff]
    clause = ""
    if category:
        clause = " AND s.source_category=%s"
        params.append(category)
    with store._connect() as con, con.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT p.marketplace,p.external_id,p.title,p.image_url,p.product_url,
                   s.source_category,s.rank,s.price,s.currency,s.observed_at
            FROM market_radar_products p
            JOIN market_radar_snapshots s ON s.product_id=p.id
            WHERE p.marketplace='MERCADO_LIVRE' AND s.observed_at >= %s
        """+clause+" ORDER BY s.observed_at DESC LIMIT 5000",params)
        rows=cur.fetchall()
    return {**build_window(rows, hours, sort=sort, min_rank=top),
            "marketplace": marketplace, "category":category,"data_source":"MERCADO_LIVRE_OFFICIAL_HIGHLIGHTS_SNAPSHOTS"}


@router.get("/mercado-livre/top")
def mercado_livre_top(category: str | None = None, period: str = Query("1d", pattern="^(1d|3d|7d|15d|30d|60d|90d)$")):
    store = hosted_market_store()
    if store:
        return _with_period(store.top(category=category, limit=20), period)
    with db.connect() as con:
        return _with_period(get_top_products(con, marketplace=Marketplace.MERCADO_LIVRE, category=category, limit=20), period)


@router.get("/mercado-livre/trends")
def mercado_livre_trends(category: str | None = None):
    store = hosted_market_store()
    if store:
        return store.trends(category=category)
    with db.connect() as con:
        return get_market_trends(con, marketplace=Marketplace.MERCADO_LIVRE, category=category)


class MercadoLivreCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_id: str = Field(min_length=3, max_length=64, pattern="^MLB[0-9]+$")
    collect_best_sellers: bool = True
    collect_trends: bool = True


class MercadoLivreDiagnosticRecord(BaseModel):
    """A bounded, server-side-only read of official commercial fields."""
    external_id: str = Field(min_length=4, max_length=64, pattern="^MLB(U)?[0-9]+$")
    ranking_type: Literal["ITEM", "PRODUCT", "USER_PRODUCT"]


class MercadoLivreDiagnosticRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[MercadoLivreDiagnosticRecord] = Field(min_length=1, max_length=5)


def _official_probe(client, path: str, *, params: dict[str, str] | None = None) -> tuple[str, object | None]:
    """Return an auditable availability code without exposing upstream bodies."""
    try:
        return "AVAILABLE", client.get(path, params)
    except MercadoLivreError as exc:
        return getattr(exc, "code", "EXTERNAL_FAILURE"), None


@router.post("/mercado-livre/diagnose-records")
def diagnose_mercado_livre_records(payload: MercadoLivreDiagnosticRequest, request: Request):
    """Audit up to five persisted-ranking identities using official read APIs.

    It does not create rankings, snapshots, orders, or any customer data.  The
    endpoint is operator-protected because it uses the server-held OAuth token.
    """
    _require_market_radar_control(request)
    client = MercadoLivreAdapter().client
    audited = []
    for record in payload.records:
        identifier = record.external_id
        kind = record.ranking_type
        detail_path = f"/items/{identifier}" if kind == "ITEM" else (
            f"/products/{identifier}" if kind == "PRODUCT" else f"/user-products/{identifier}")
        detail_status, detail = _official_probe(client, detail_path)
        result: dict[str, object] = {
            "external_id": identifier, "ranking_type": kind,
            "detail_status": detail_status,
            "price_status": "NOT_APPLICABLE", "visits_status": "NOT_APPLICABLE",
            "sold_quantity_status": "NOT_APPLICABLE",
        }
        if isinstance(detail, dict):
            result["title"] = detail.get("title") or detail.get("name")
            result["image_url"] = detail.get("thumbnail")
            result["product_url"] = detail.get("permalink")
            # This field, if present, is an item's accumulated quantity; it is
            # never presented as sales in a requested time window.
            if kind == "ITEM":
                result["sold_quantity_status"] = "AVAILABLE" if detail.get("sold_quantity") is not None else "UNAVAILABLE"
                result["sold_quantity"] = detail.get("sold_quantity")
        if kind == "ITEM":
            price_status, prices = _official_probe(client, f"/items/{identifier}/prices")
            result["price_status"] = price_status
            if isinstance(prices, list):
                current = next((entry for entry in prices if isinstance(entry, dict) and entry.get("amount") is not None), None)
                if current:
                    result["price"] = current.get("amount")
                    result["currency"] = current.get("currency_id")
            visits_status, visits = _official_probe(client, f"/items/{identifier}/visits/time_window", params={"last": "2", "unit": "day"})
            result["visits_status"] = visits_status
            if isinstance(visits, dict):
                # Store exactly the source response's aggregate only when it is
                # explicitly supplied. No conversion or sales inference occurs.
                result["visits"] = visits.get("total_visits")
        audited.append(result)
    return {"records": audited, "orders_checked": False, "snapshots_written": 0}


@router.post("/mercado-livre/collect")
def collect_mercado_livre(payload: MercadoLivreCollectionRequest, request: Request):
    _require_market_radar_control(request)
    if not payload.collect_best_sellers and not payload.collect_trends:
        raise HTTPException(422, "Choose at least one official Mercado Livre collection")
    store = hosted_market_store()
    if store:
        return store.collect(MercadoLivreAdapter(), category=payload.category_id, limit=20, collect_trends=payload.collect_trends)
    with db.connect() as con:
        return run_marketplace_collection(con, marketplace=Marketplace.MERCADO_LIVRE, category=payload.category_id,
                                          limit=20, collect_best_sellers=payload.collect_best_sellers,
                                          collect_trends=payload.collect_trends)


@router.get("/mercado-livre/categories")
def mercado_livre_categories(request: Request, parent_id: str | None = Query(None, pattern="^MLB[0-9]+$")):
    """Protected, sanitized official category-tree reader for manual ranking runs."""
    _require_market_radar_control(request)
    client = MercadoLivreAdapter().client
    if parent_id:
        payload = client.get(f"/categories/{parent_id}")
        children = payload.get("children_categories", []) if isinstance(payload, dict) else []
        parent = {"id": payload.get("id"), "name": payload.get("name"), "is_leaf": not bool(children)} if isinstance(payload, dict) else None
    else:
        children = client.get("/sites/MLB/categories")
        parent = {"id": "MLB", "name": "Brasil", "is_leaf": False}
    if not isinstance(children, list):
        raise HTTPException(502, "Mercado Livre returned an invalid category response")
    return {"parent": parent, "categories": [
        {"id": item.get("id"), "name": item.get("name"), "is_leaf": False}
        for item in children if isinstance(item, dict) and item.get("id") and item.get("name")
    ]}


@router.post("/mercado-livre/enrich-existing")
def enrich_mercado_livre_existing(payload: MercadoLivreCollectionRequest, request: Request):
    """Bounded repair for persisted official rankings; never fetches a new ranking."""
    _require_market_radar_control(request)
    store = hosted_market_store()
    if not store:
        raise HTTPException(409, "Hosted Market Radar storage is required")
    return store.enrich_existing(MercadoLivreAdapter(), category=payload.category_id, limit=20)


@router.get("/mercado-livre/auth/status")
def mercado_livre_auth_status():
    settings = mercado_livre_auth_config()
    return {"app_configured": settings.app_configured, "authorized": bool(settings.access_token),
            "refresh_available": bool(settings.refresh_token), "storage": storage_mode()}


@router.post("/mercado-livre/auth/start")
def mercado_livre_auth_start(request: Request):
    _require_market_radar_control(request)
    try:
        return start_authorization()
    except MercadoLivreOAuthError as exc:
        raise HTTPException(409, "Mercado Livre authorization configuration is required") from exc


@router.get("/mercado-livre/auth/grants")
def mercado_livre_auth_grants():
    """Sanitized grant audit; the official API bearer stays server-side.

    Unlike control actions this is read-only and exposes only aggregate scope
    flags, never token material or granted account identifiers.
    """
    try:
        return authorization_grants_summary()
    except MercadoLivreOAuthError as exc:
        raise HTTPException(409, "Mercado Livre grants are unavailable") from exc


@router.get("/mercado-livre/auth/callback")
def mercado_livre_auth_callback(code: str, state: str):
    try:
        return {"authorized": True, **exchange_code(code=code, state=state)}
    except MercadoLivreOAuthError as exc:
        raise HTTPException(400, "Mercado Livre authorization could not be completed") from exc


@router.post("/mercado-livre/auth/refresh")
def mercado_livre_auth_refresh(request: Request):
    _require_market_radar_control(request)
    try:
        return {"authorized": True, **refresh_mercado_livre_token()}
    except MercadoLivreOAuthError as exc:
        raise HTTPException(409, "Mercado Livre refresh authorization is required") from exc


@router.get("/mercado-livre/probe")
def mercado_livre_probe():
    try:
        result = MercadoLivreAdapter().client.probe()
        if result.get("site_id") not in (None, "MLB"):
            raise HTTPException(409, "The configured account is not an MLB account")
        return {"status": "OK", "site_id": result.get("site_id")}
    except MercadoLivreError as exc:
        raise HTTPException(409, "Mercado Livre authorization is required or unavailable") from exc
