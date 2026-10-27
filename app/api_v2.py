"""Small, read-only product-facing API adapters for UI V2.

This module deliberately does not schedule browser work, recompute intelligence,
or expose bridge/security implementation details.  It translates persisted read
models into a compact contract intended for the product home.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter

from .db import connect


router = APIRouter(prefix="/api/v2")


def _table_exists(con, name: str) -> bool:
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _parse_stamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _presentation_quality(row: dict[str, Any], metrics: dict[str, Any]) -> str:
    fields = (row.get("thumbnail_url"), row.get("creator_username"), row.get("caption"), row.get("canonical_url"))
    filled = sum(bool(value) for value in fields) + sum(value is not None for value in metrics.values())
    if filled >= 5:
        return "COMPLETE"
    if filled >= 2:
        return "PARTIAL"
    return "MINIMAL"


def _labels(opportunity: dict[str, Any]) -> dict[str, str]:
    lifecycle = opportunity.get("lifecycle", "DISCOVERED")
    return {
        "lifecycle_label": {
            "EARLY_SIGNAL": "Sinal inicial", "EMERGING": "Em alta", "ACCELERATING": "Acelerando",
            "BREAKOUT": "Em expansão", "MAINSTREAM": "Popular", "SATURATED": "Saturado",
            "DECLINING": "Perdendo força", "DISCOVERED": "Descoberto",
        }.get(lifecycle, "Dados insuficientes"),
        "movement_label": {
            "RISING": "Ganhando força", "STABLE": "Estável", "FALLING": "Perdendo força",
        }.get(opportunity.get("velocity_summary"), "Ainda não sabemos"),
        "saturation_label": {"LOW": "Baixa", "MEDIUM": "Média", "HIGH": "Alta"}.get(
            opportunity.get("saturation"), "Dados insuficientes"
        ),
    }


_FRIENDLY_PRODUCT_NAMES = {
    "soap dispenser": "Dispenser de sabão",
    "dish brush": "Escova para louças",
    "long-handled floor brush": "Escova de chão com cabo longo",
}


def _friendly_name(name: str) -> str:
    """Use only a small, explicit presentation mapping; never infer a name."""
    return _FRIENDLY_PRODUCT_NAMES.get(name.casefold(), name)


def _top_opportunities(con) -> list[dict[str, Any]]:
    if not _table_exists(con, "top_opportunities"):
        return []
    rows = con.execute("SELECT result_json FROM top_opportunities ORDER BY computed_at DESC").fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        try:
            opportunity = json.loads(row["result_json"])
        except (TypeError, ValueError, KeyError):
            continue
        why = [entry.get("text") if isinstance(entry, dict) else str(entry) for entry in opportunity.get("why", [])]
        labels = _labels(opportunity)
        items.append({
            "id": str(opportunity.get("candidate_id", "")),
            "name": _friendly_name(opportunity.get("display_name") or "Produto sem nome identificado"),
            "original_name": opportunity.get("display_name"),
            "lifecycle": opportunity.get("lifecycle", "DISCOVERED"),
            **labels,
            "observation_count": opportunity.get("observation_count", 0),
            "query_spread": opportunity.get("query_spread", 0),
            "creator_spread": opportunity.get("creator_spread", 0),
            "why": why[:3],
        })
    # Keep the existing engine's lifecycle/momentum output; only sort presentation.
    priority = {"BREAKOUT": 0, "ACCELERATING": 1, "EMERGING": 2, "EARLY_SIGNAL": 3, "DISCOVERED": 4}
    return sorted(items, key=lambda item: (priority.get(item["lifecycle"], 9), -item["observation_count"]))[:3]


def _recent_discoveries(con) -> list[dict[str, Any]]:
    if not _table_exists(con, "videos"):
        return []
    rows = con.execute("""
        SELECT v.*, o.search_query, o.observed_at, o.fields_json
        FROM videos v
        LEFT JOIN search_observations o ON o.id=(
            SELECT latest.id FROM search_observations latest
            WHERE latest.video_id=v.id ORDER BY latest.observed_at DESC, latest.id DESC LIMIT 1
        )
        ORDER BY v.first_seen_at DESC, v.id DESC
        LIMIT 20
    """).fetchall()
    discoveries: list[dict[str, Any]] = []
    for sqlite_row in rows:
        row = dict(sqlite_row)
        try:
            fields = json.loads(row.get("fields_json") or "{}")
        except (TypeError, ValueError):
            fields = {}
        metrics = {key: fields.get(key) for key in ("views", "likes", "comments_count", "shares", "favorites") if fields.get(key) is not None}
        product_name = None
        if _table_exists(con, "product_candidate_evidence") and _table_exists(con, "product_candidates"):
            product = con.execute("""
                SELECT c.canonical_name FROM product_candidate_evidence e
                JOIN product_candidates c ON c.id=e.candidate_id
                WHERE e.video_id=? AND c.canonical_name<>''
                ORDER BY e.observed_at DESC, c.id DESC LIMIT 1
            """, (row["id"],)).fetchone()
            product_name = product[0] if product else None
        # Home is a curated surface: a thumbnail by itself is not a discovery.
        if not (row.get("thumbnail_url") and (row.get("creator_username") or row.get("caption")) and (product_name or metrics)):
            continue
        discoveries.append({
            "video_id": row.get("video_id") or str(row["id"]),
            "thumbnail_url": row.get("thumbnail_url"),
            "creator": row.get("creator_username") or row.get("creator_display_name"),
            "caption": row.get("caption"),
            "product_name": _friendly_name(product_name) if product_name else None,
            "detected_at": row.get("first_seen_at"),
            "query": row.get("search_query"),
            "metrics": metrics,
            "data_quality": _presentation_quality(row, metrics),
        })
        if len(discoveries) == 3:
            break
    return discoveries


def _last_mission(con) -> dict[str, Any] | None:
    if not _table_exists(con, "viral_products_72h_missions"):
        return None
    row = con.execute("SELECT * FROM viral_products_72h_missions ORDER BY updated_at DESC LIMIT 1").fetchone()
    if not row:
        return None
    data = dict(row)
    try:
        query_count = len(json.loads(data.get("queries_json") or "[]"))
    except (TypeError, ValueError):
        query_count = 0
    return {
        "name": "Descoberta de sinais emergentes",
        "status": data.get("status"),
        "queries": query_count,
        "results": data.get("results", 0),
        "new_videos": data.get("new_videos", 0),
        "duplicates": data.get("duplicates", 0),
        "finished_at": data.get("updated_at"),
    }


def home_read_model(con, now: datetime | None = None) -> dict[str, Any]:
    """Build the home response from persisted data without writing to SQLite."""
    now = now or datetime.now(timezone.utc)
    videos = int(con.execute("SELECT COUNT(*) FROM videos").fetchone()[0]) if _table_exists(con, "videos") else 0
    cutoff = (now - timedelta(hours=24)).isoformat()
    recently_detected = int(con.execute("SELECT COUNT(*) FROM videos WHERE first_seen_at>=?", (cutoff,)).fetchone()[0]) if _table_exists(con, "videos") else 0
    identified_products = 0
    if _table_exists(con, "product_candidates"):
        identified_products = int(con.execute("""
            SELECT COUNT(*) FROM product_candidates
            WHERE canonical_name<>'' AND (status IN ('corroborated','promoted') OR manual_status='confirmed')
        """).fetchone()[0])
    opportunities = _top_opportunities(con)
    freshness = None
    if _table_exists(con, "search_observations"):
        row = con.execute("SELECT MAX(observed_at) FROM search_observations").fetchone()
        freshness = row[0] if row else None
    return {
        "generated_at": now.isoformat(),
        "summary": {
            "library_videos": videos,
            "recently_detected": recently_detected,
            "identified_products": identified_products,
            "strong_signals": len(opportunities),
        },
        "pulse": {
            "signal_count": len(opportunities),
            "rising_count": sum(item["movement_label"] == "Ganhando força" for item in opportunities),
            "new_signal_count": sum(item["lifecycle"] in ("EARLY_SIGNAL", "DISCOVERED") for item in opportunities),
        },
        "top_opportunities": opportunities,
        "recent_discoveries": _recent_discoveries(con),
        "last_mission": _last_mission(con),
        "data_freshness": {"last_observation_at": freshness},
    }


@router.get("/home")
def home():
    with connect() as con:
        return home_read_model(con)
