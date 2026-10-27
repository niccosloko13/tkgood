from __future__ import annotations

from datetime import datetime, timezone

from .adapters import adapters
from .capabilities import as_dict, source_confidence
from .models import Marketplace, RunStatus
from .ranking import top_products
from .repository import create_run, finish_run, save_observation, save_search_trends, search_trends, set_source_state
from .adapters.mercado_livre import MercadoLivreAuthError, MercadoLivreCategoryNotRanked, MercadoLivreError
from .mercado_livre_auth import config as mercado_livre_auth_config


def adapter_registry():
    return {adapter.marketplace: adapter for adapter in adapters()}


def sources_read_model(con) -> list[dict]:
    registry = adapter_registry()
    rows = {row["marketplace"]: row for row in con.execute("SELECT * FROM market_source_state").fetchall()} if _table_exists(con, "market_source_state") else {}
    sources = []
    for marketplace, adapter in registry.items():
        stored = rows.get(marketplace.value)
        status = "AVAILABLE" if adapter.available else "AUTH_REQUIRED" if marketplace == Marketplace.MERCADO_LIVRE and mercado_livre_auth_config().app_configured else "NOT_CONFIGURED"
        sources.append({"marketplace": marketplace.value, "label": marketplace.value.replace("_", " ").title(),
                        "status": status, "available": bool(adapter.available),
                        "capabilities": as_dict(adapter.capabilities()), "source_type": adapter.source_type.value,
                        "source_confidence": source_confidence(adapter.source_type).value,
                        "last_success_at": stored["last_success_at"] if stored else None, "last_error_at": stored["last_error_at"] if stored else None})
    return sources


def _table_exists(con, name: str) -> bool:
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def run_marketplace_collection(con, *, marketplace: Marketplace, category: str | None = None, limit: int = 20,
                               collect_best_sellers: bool = True, collect_trends: bool = False) -> dict:
    """Manual collection with bounded official calls and sanitized failure records."""
    limit = min(max(1, limit), 20)
    adapter = adapter_registry()[marketplace]
    run_id = create_run(con, marketplace.value, category, limit)
    confidence = source_confidence(adapter.source_type).value
    set_source_state(con, marketplace.value, available=adapter.available, capabilities=as_dict(adapter.capabilities()), source_type=adapter.source_type.value, source_confidence=confidence, error=None if adapter.available else "adapter unavailable")
    if not adapter.available:
        finish_run(con, run_id, RunStatus.UNAVAILABLE, error_message="adapter unavailable")
        return {"id": run_id, "status": RunStatus.UNAVAILABLE.value, "received_count": 0, "error": "adapter unavailable"}
    try:
        observations = adapter.fetch_top_products(category=category, limit=limit) if collect_best_sellers else []
        for observation in observations: save_observation(con, observation)
        trend_count = 0
        if collect_trends:
            fetch_trends = getattr(adapter, "fetch_trends", None)
            if fetch_trends is None:
                raise MercadoLivreError("adapter does not support trends")
            trend_count = save_search_trends(con, fetch_trends(category=category))
        partial_count = sum(1 for item in observations if not item.evidence.get("detail_resolved", True))
        status = RunStatus.PARTIAL if partial_count else RunStatus.COMPLETED
        finish_run(con, run_id, status, len(observations), enriched_count=len(observations) - partial_count,
                   partial_count=partial_count, failure_count=partial_count)
        set_source_state(con, marketplace.value, available=True, capabilities=as_dict(adapter.capabilities()), source_type=adapter.source_type.value, source_confidence=confidence)
        return {"id": run_id, "status": status.value, "received_count": len(observations), "enriched_count": len(observations) - partial_count,
                "partial_count": partial_count, "failure_count": partial_count, "trend_count": trend_count}
    except MercadoLivreAuthError:
        finish_run(con, run_id, RunStatus.FAILED, error_message="AUTH_REQUIRED", failure_count=1)
        set_source_state(con, marketplace.value, available=False, capabilities=as_dict(adapter.capabilities()), source_type=adapter.source_type.value, source_confidence=confidence, error="AUTH_REQUIRED")
        return {"id": run_id, "status": RunStatus.FAILED.value, "received_count": 0, "error": "AUTH_REQUIRED"}
    except MercadoLivreCategoryNotRanked:
        finish_run(con, run_id, RunStatus.PARTIAL, error_message="CATEGORY_NOT_RANKED", failure_count=1)
        set_source_state(con, marketplace.value, available=True, capabilities=as_dict(adapter.capabilities()), source_type=adapter.source_type.value, source_confidence=confidence, error="CATEGORY_NOT_RANKED")
        return {"id": run_id, "status": RunStatus.PARTIAL.value, "received_count": 0, "error": "CATEGORY_NOT_RANKED"}
    except MercadoLivreError:
        finish_run(con, run_id, RunStatus.FAILED, error_message="EXTERNAL_FAILURE", failure_count=1)
        set_source_state(con, marketplace.value, available=True, capabilities=as_dict(adapter.capabilities()), source_type=adapter.source_type.value, source_confidence=confidence, error="EXTERNAL_FAILURE")
        return {"id": run_id, "status": RunStatus.FAILED.value, "received_count": 0, "error": "EXTERNAL_FAILURE"}


def get_top_products(con, *, marketplace: Marketplace, category: str | None = None, limit: int = 20) -> dict:
    products = top_products(con, marketplace=marketplace.value, category=category, limit=limit)
    first = min((item["first_seen_at"] for item in products if item["first_seen_at"]), default=None)
    requested_window = None
    return {"marketplace": marketplace.value, "category": category, "limit": min(max(1, limit), 20), "history_available_from": first, "products": products,
            "requested_window": requested_window, "history_complete": False if not first else None,
            "observation_window": {"from": first, "to": datetime.now(timezone.utc).isoformat() if first else None}}


def get_market_trends(con, *, marketplace: Marketplace, category: str | None = None) -> dict:
    values = search_trends(con, marketplace=marketplace.value, category=category)
    return {"marketplace": marketplace.value, "category": category, "source_window": "weekly", "trends": values}
