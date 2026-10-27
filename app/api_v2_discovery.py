"""Read and action adapters for the V2 Discovery screen.

The adapters intentionally delegate all browser work to DiscoveryRunner.  They
never relax its validation, budget, or explicit-authorization rules.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from . import db
from .discovery_runner import DiscoveryRunner
from .intelligence_api import local_write
from .session_api import connection_read_model


router = APIRouter(prefix="/api/v2/discovery")

PRESETS = (
    {"id": "gaining-strength", "name": "Produtos ganhando força", "description": "Busca sinais emergentes em diferentes tipos de pesquisa.", "queries": ["home gadgets", "home finds", "useful home products", "kitchen gadgets", "cleaning gadgets"]},
    {"id": "home", "name": "Casa", "description": "Procura produtos úteis para diferentes contextos da casa.", "queries": ["home gadgets", "home finds", "amazon home finds", "useful home products", "viral home products"]},
    {"id": "kitchen", "name": "Cozinha", "description": "Procura utensílios e gadgets de cozinha.", "queries": ["kitchen gadgets", "kitchen finds"]},
    {"id": "cleaning", "name": "Limpeza", "description": "Procura produtos e gadgets de limpeza.", "queries": ["cleaning gadgets", "laundry gadgets"]},
    {"id": "gadgets", "name": "Gadgets", "description": "Explora gadgets úteis para o dia a dia.", "queries": ["home gadgets", "smart home gadgets", "kitchen gadgets"]},
)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=200)


class MissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    preset_id: str = Field(min_length=1, max_length=64)


def _table(con, name: str) -> bool:
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _batch_products(con, batch_id: str) -> int | None:
    if not all(_table(con, name) for name in ("product_candidates", "product_candidate_evidence", "bridge_commands", "search_observations")):
        return None
    row = con.execute("""
        SELECT count(DISTINCT e.candidate_id)
        FROM product_candidate_evidence e
        JOIN search_observations o ON o.video_id=e.video_id
        JOIN bridge_commands b ON o.capture_id='command:' || b.id
        WHERE json_extract(b.options_json,'$.safe_collection_id')=?
    """, (batch_id,)).fetchone()
    return int(row[0]) if row else None


def _batch_view(con, row) -> dict[str, Any]:
    report = DiscoveryRunner.report(con, row["id"])
    if not report:
        return {}
    queries = report["queries"]
    index = report["query_index"]
    current = queries[index - 1] if report["status"] == "PENDING" and index else None
    return {
        "status": report["status"], "queries_total": len(queries), "queries_completed": max(0, index - (1 if current else 0)),
        "current_query": current, "results": report["results"], "new_videos": report["new_videos"],
        "duplicates": report["duplicates"], "identified_products": _batch_products(con, row["id"]),
        "stop_reason": report["stop_reason"], "finished_at": report["checkpoint"]["completed_at"],
    }


def _query_performance(con) -> list[dict[str, Any]]:
    if not _table(con, "search_captures"):
        return []
    rows = con.execute("""
        SELECT search_query, sum(COALESCE(new_count,0)) AS new_videos,
          sum(COALESCE(updated_count,0)) AS duplicates,
          sum(COALESCE(new_count,0)+COALESCE(updated_count,0)) AS total,
          max(observed_at) AS observed_at
        FROM search_captures GROUP BY search_query HAVING total>0
        ORDER BY (1.0 * sum(COALESCE(new_count,0)) / sum(COALESCE(new_count,0)+COALESCE(updated_count,0))) DESC,
          max(observed_at) DESC LIMIT 5
    """).fetchall()
    return [{
        "query": row["search_query"], "total": int(row["total"]), "new_videos": int(row["new_videos"]),
        "duplicates": int(row["duplicates"]), "novelty_rate": row["new_videos"] / row["total"] if row["total"] else None,
    } for row in rows]


def discovery_read_model(con, bridge: dict, security_stop: dict | None) -> dict[str, Any]:
    connection = connection_read_model(bridge, security_stop)
    active = last = None
    if _table(con, "safe_collection_batches"):
        active_row = con.execute("SELECT * FROM safe_collection_batches WHERE status IN ('READY','PENDING') ORDER BY created_at DESC LIMIT 1").fetchone()
        last_row = con.execute("SELECT * FROM safe_collection_batches ORDER BY created_at DESC LIMIT 1").fetchone()
        active = _batch_view(con, active_row) if active_row else None
        last = _batch_view(con, last_row) if last_row else None
    presets = [{"id": item["id"], "name": item["name"], "description": item["description"], "query_count": len(item["queries"])} for item in PRESETS]
    return {
        "connection": {"ready": connection["status"] == "CONNECTED", "status": connection["status"],
                       "label": "Babi pronta para pesquisar" if connection["status"] == "CONNECTED" else "Ação necessária no TikTok"},
        "active_run": active, "last_run": last, "presets": presets, "query_performance": _query_performance(con),
    }


@router.get("")
def discovery_state():
    from .main import live_bridge
    with db.connect() as con:
        return discovery_read_model(con, live_bridge(), db.get_state("browser_security_stop", {}))


def _released_validation(con):
    row = con.execute("SELECT id FROM safe_recovery_checks WHERE release_json IS NOT NULL ORDER BY validated_at DESC LIMIT 1").fetchone()
    if not row:
        raise HTTPException(409, "Ação necessária no TikTok antes de iniciar uma descoberta.")
    return row["id"]


@router.post("/search")
def search(body: SearchRequest, request: Request):
    local_write(request)
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        validation_id = _released_validation(con)
        return DiscoveryRunner.start(con, validation_id, [body.query.strip()], 1, allow_explicit_unobserved=True)


@router.post("/mission")
def mission(body: MissionRequest, request: Request):
    local_write(request)
    preset = next((item for item in PRESETS if item["id"] == body.preset_id), None)
    if not preset:
        raise HTTPException(404, "Missão não encontrada")
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        # A Stage 2 mission is possible only after the pre-existing explicit
        # authorization for precisely this pack.  The UI cannot manufacture it.
        authorization = con.execute("SELECT * FROM safe_stage2_authorizations ORDER BY authorized_at DESC").fetchall()
        match = next((row for row in authorization if json.loads(row["queries_json"]) == preset["queries"]), None)
        if not match:
            raise HTTPException(409, "Esta missão precisa de uma autorização segura atual antes de começar.")
        return DiscoveryRunner.start(con, match["validation_id"], preset["queries"], 2)
