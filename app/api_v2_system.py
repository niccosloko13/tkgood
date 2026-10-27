"""Read-only operational summary for the product-facing System V2 screen."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from . import db
from .api_v2 import _presentation_quality, _table_exists
from .collection_mode import direct
from .market_radar.service import sources_read_model
from .session_api import connection_read_model


router = APIRouter(prefix="/api/v2")


def _event_label(event_type: str, level: str) -> str:
    labels = {
        "security_stop": "Ação necessária no TikTok",
        "security_recovery": "Revisão de segurança concluída",
        "session": "Sessão do TikTok atualizada",
        "browser": "Navegador atualizado",
        "health": "Estado da conexão atualizado",
        "safe_collection": "Busca concluída",
        "discovery": "Descoberta atualizada",
    }
    return labels.get(event_type, "Evento do sistema" if level != "ERROR" else "Atenção necessária")


def _data_quality(con) -> dict[str, int]:
    if not _table_exists(con, "videos"):
        return {"videos": 0, "complete": 0, "partial": 0, "minimal": 0}
    observations = _table_exists(con, "search_observations")
    latest = "NULL AS fields_json" if not observations else """
      (SELECT fields_json FROM search_observations o WHERE o.video_id=v.id
       ORDER BY observed_at DESC,id DESC LIMIT 1) AS fields_json
    """
    rows = con.execute(f"SELECT v.*, {latest} FROM videos v").fetchall()
    counts = {"videos": len(rows), "complete": 0, "partial": 0, "minimal": 0}
    for row in rows:
        # The presentation quality needs only visible metadata. It intentionally
        # does not alter or claim evidence-engine quality.
        import json
        try:
            metrics = json.loads(row["fields_json"] or "{}")
        except (TypeError, ValueError):
            metrics = {}
        visible_metrics = {key: metrics.get(key) for key in ("views", "likes", "comments_count", "shares", "favorites") if metrics.get(key) is not None}
        state = _presentation_quality(dict(row), visible_metrics).lower()
        counts[state] += 1
    return counts


def _events(con) -> list[dict[str, str | None]]:
    if not _table_exists(con, "events"):
        return []
    rows = con.execute("SELECT created_at,event_type,level FROM events ORDER BY id DESC LIMIT 5").fetchall()
    return [{"at": row["created_at"], "label": _event_label(row["event_type"], row["level"]), "level": row["level"]} for row in rows]


def system_read_model(con, bridge: dict[str, Any], security_stop: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    connection = connection_read_model(bridge, security_stop)
    blocked = connection["security"] == "BLOCKED"
    connected = connection["status"] == "CONNECTED"
    overall = {"status": "HEALTHY", "label": "Tudo funcionando normalmente"} if connected and not blocked else {
        "status": "ATTENTION", "label": "Ação necessária" if blocked else "Verifique a conexão"
    }
    direct_state = direct(con) if _table_exists(con, "system_state") else {"status": "ENABLED", "reason": None}
    return {
        "generated_at": now.isoformat(),
        "overall": overall,
        "browser": {"status": connection["browser"], "label": "Conectado" if connection["browser"] == "ONLINE" else "Indisponível"},
        "tiktok": {"status": connection["tiktok"], "label": "Pronto para pesquisa" if connection["tiktok"] == "CONNECTED" else "Atenção necessária"},
        "session": {"status": connection["session"], "label": "Confirmada" if connection["session"] == "CONFIRMED" else "Login necessário" if connection["session"] == "LOGGED_OUT" else "Atenção necessária"},
        "security": {"status": connection["security"], "label": "Nenhum bloqueio ativo" if not blocked else "Ação necessária no TikTok"},
        "backend": {"status": "ONLINE", "label": "Funcionando"},
        "direct_video_enrichment": {"status": direct_state.get("status", "ENABLED"), "label": "Pausada" if direct_state.get("status") == "PAUSED" else "Disponível", "reason": direct_state.get("reason")},
        "database": {"status": "ONLINE", "label": "Funcionando"},
        "data_quality": _data_quality(con),
        "events": _events(con),
        "external_sources": [{"name": item["label"], "status": "Disponível" if item["available"] else "Autorização necessária" if item.get("status") == "AUTH_REQUIRED" else "Configuração necessária"}
                             for item in sources_read_model(con)],
        "laboratory": [{"name": name, "status": "Disponível apenas para revisão técnica"} for name in ("Gold Set", "Identificação visual", "OpenCLIP", "FAISS", "Inteligência experimental")],
        "diagnostics": {
            "bridge": {"connected": bool(bridge.get("connected")), "heartbeat_fresh": bool(bridge.get("heartbeat_fresh")), "last_seen": bridge.get("last_seen"), "build": bridge.get("build_id")},
            "tiktok": {"current_url": bridge.get("current_url"), "page_state": bridge.get("current_page_status"), "session_state": bridge.get("tiktok_session_status")},
            "security": {"latch_active": blocked, "reason": (security_stop or {}).get("reason")},
            "backend": {"run_id": bridge.get("backend_run_id")},
        },
    }


@router.get("/system")
def system_state():
    from .main import live_bridge
    with db.connect() as con:
        return system_read_model(con, live_bridge(), db.get_state("browser_security_stop", {}))
