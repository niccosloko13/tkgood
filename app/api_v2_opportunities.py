"""Read-only presentation adapter for persisted Trend Engine opportunities."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from .api_v2 import _friendly_name, _labels, _table_exists
from .db import connect

router = APIRouter(prefix="/api/v2")


def _texts(entries: list[dict[str, Any]] | None) -> list[str]:
    return [entry.get("text", "") for entry in entries or [] if entry.get("text")]


def _opportunity(item: dict[str, Any], events: list[dict[str, Any]], related_video_count: int = 0) -> dict[str, Any]:
    name = item.get("display_name") or "Produto sem nome identificado"
    related = [event for event in events if str(event.get("candidate_id")) == str(item.get("candidate_id"))]
    labels = _labels(item)
    return {
        "id": str(item.get("candidate_id")), "name": _friendly_name(name), "display_name": _friendly_name(name), "original_name": name,
        "state": {"lifecycle": item.get("lifecycle", "DISCOVERED"), "label": labels["lifecycle_label"],
                  "movement": labels["movement_label"], "saturation": labels["saturation_label"]},
        "metrics": {"observations": item.get("observation_count", 0), "queries": item.get("query_spread", 0), "creators": item.get("creator_spread", 0)},
        "related_video_count": related_video_count,
        "why": _texts(item.get("why"))[:4], "limits": _texts(item.get("risks")) + _texts(item.get("insufficient_signals")),
        "history": {"first_detected_at": item.get("first_seen"), "last_observed_at": item.get("last_seen"),
                    "changes": [{"type": event.get("event_type"), "at": event.get("observed_at")} for event in related[:5]]},
        "advanced": {"lifecycle": item.get("lifecycle"), "momentum": item.get("momentum"),
                     "velocity": item.get("velocity_summary"), "acceleration": item.get("acceleration_summary"),
                     "saturation": item.get("saturation"), "evidence_quality": item.get("evidence_quality"),
                     "duplicate_density": item.get("duplicate_density"), "source_count": len(item.get("observation_ids", []))},
    }


def opportunities_read_model(con, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if not _table_exists(con, "top_opportunities"):
        return {"generated_at": now.isoformat(), "summary": {"total": 0, "strong": 0, "watching": 0, "saturated": 0}, "top": [], "watchlist": [], "saturated": []}
    raw = []
    for row in con.execute("SELECT result_json FROM top_opportunities"):
        try:
            raw.append(json.loads(row["result_json"]))
        except (TypeError, ValueError, KeyError):
            continue
    events = []
    if _table_exists(con, "trend_change_events"):
        events = [dict(row) for row in con.execute("SELECT candidate_id,event_type,observed_at FROM trend_change_events ORDER BY id DESC LIMIT 100")]
    related_counts: dict[str, int] = {}
    if _table_exists(con, "product_candidate_evidence"):
        related_counts = {str(row["candidate_id"]): row["count"] for row in con.execute(
            "SELECT candidate_id,COUNT(DISTINCT video_id) AS count FROM product_candidate_evidence WHERE video_id IS NOT NULL GROUP BY candidate_id"
        )}
    items = [_opportunity(item, events, related_counts.get(str(item.get("candidate_id")), 0)) for item in raw]
    priority = {"Em expansão": 0, "Acelerando": 1, "Em alta": 2, "Sinal inicial": 3, "Descoberto": 4, "Popular": 5, "Saturado": 6, "Perdendo força": 7}
    items.sort(key=lambda item: (priority.get(item["state"]["label"], 9), -item["metrics"]["observations"]))
    saturated = [item for item in items if item["state"]["lifecycle"] == "SATURATED" or item["state"]["saturation"] == "Alta"]
    strong = [item for item in items if item not in saturated and item["state"]["lifecycle"] in ("BREAKOUT", "ACCELERATING", "EMERGING") and item["advanced"]["evidence_quality"] in ("HIGH", "MEDIUM")]
    watchlist = [item for item in items if item not in strong and item not in saturated]
    return {"generated_at": now.isoformat(), "summary": {"total": len(items), "strong": len(strong), "watching": len(watchlist), "saturated": len(saturated)}, "top": strong, "watchlist": watchlist, "saturated": saturated}


@router.get("/opportunities")
def opportunities():
    with connect() as con:
        return opportunities_read_model(con)
