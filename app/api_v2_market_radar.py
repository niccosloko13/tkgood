from datetime import datetime, timedelta, timezone
import hmac
import os

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
