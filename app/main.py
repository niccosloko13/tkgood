from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from .schemas import BridgeHeartbeat, SearchCommand, CommandResult
from .db import enqueue_search, list_commands, claim_command, finish_command

from .chrome_launcher import open_tiktok_in_normal_chrome
from .db import (
    create_mission,
    get_state,
    init_db,
    latest_mission,
    log_event,
    recent_events,
    set_state,
)
from .schemas import MissionCreate

app = FastAPI(title="Product Hunter — TikTok")


def live_bridge():
    bridge = get_state("tiktok_bridge", {}) or {}
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(bridge["last_seen"])).total_seconds()
        connected = 0 <= age < 75
    except (KeyError, ValueError, TypeError):
        connected = False
    return {**bridge, "connected": connected,
            "extension_connected": connected,
            "chrome_connected": connected and bridge.get("chrome_connected", False),
            "tiktok_open": connected and bridge.get("tiktok_open", False),
            "authenticated_hint": connected and bridge.get("tiktok_open", False) and bridge.get("authenticated_hint", False)}


@app.on_event("startup")
def startup():
    init_db()
    log_event("system", "Product Hunter TikTok v0.1.4 started (Normal Chrome Bridge mode).")


@app.get("/", response_class=HTMLResponse)
def index():
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/status")
def status():
    return {
        "app": "online",
        "mode": "normal_chrome_bridge",
        "bridge": live_bridge(),
        "last_browser_error": get_state("browser_last_error", None),
        "latest_mission": latest_mission(),
    }


@app.post("/api/tiktok/open")
def api_open_tiktok():
    result = open_tiktok_in_normal_chrome()
    log_event("command", "Open TikTok in normal Chrome requested from dashboard.")
    return result


@app.post("/api/bridge/heartbeat")
def bridge_heartbeat(payload: BridgeHeartbeat, x_extension_id: str = Header(default="companion", min_length=1, max_length=128)):
    now = datetime.now(timezone.utc).isoformat()
    previous = live_bridge()
    state = {
        **payload.model_dump(),
        # Preserve the dashboard/command state shape; the wire body has only
        # the seven canonical heartbeat fields. Routing identity is a header.
        "extension_id": x_extension_id,
        "version": payload.extension_version,
        "chrome_connected": True,
        "tiktok_open": payload.current_url.startswith("https://www.tiktok.com/"),
        "connected": True,
        "last_seen": now,
        "url": payload.current_url,
        "title": payload.page_title,
        "authenticated_hint": payload.authenticated_hint,
        "page_signals": {
            "ready_state": payload.page_ready_state,
            "has_search": payload.has_search_ui,
            "playback_error_visible": payload.playback_error_visible,
            "content_script_connected": payload.page_ready_state is not None,
        },
    }
    set_state("tiktok_bridge", state)
    for key in ("extension_id", "chrome_connected", "tiktok_open", "authenticated_hint", "url"):
        if previous.get(key) != state.get(key) or (key == "extension_id" and not previous.get("connected")):
            log_event("bridge", f"Bridge {key}: {state.get(key)}")
    return {"ok": True, "received_at": now}


@app.get("/api/bridge/state")
def bridge_state():
    return live_bridge()


@app.post("/api/commands", status_code=201)
def create_command(payload: SearchCommand):
    try:
        query = SearchCommand.normalized_query(payload.query)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    bridge = live_bridge()
    if not bridge["chrome_connected"] or not bridge["tiktok_open"]:
        raise HTTPException(409, "Connect the Companion and open a TikTok tab first")
    command_id = enqueue_search(query, bridge["extension_id"])
    return {"id": command_id, "type": "SEARCH", "query": query, "status": "PENDING"}


@app.get("/api/commands")
def commands():
    return {"items": list_commands()}


@app.get("/api/bridge/commands/next")
def next_command(extension_id: str):
    bridge = live_bridge()
    if not bridge["connected"] or bridge.get("extension_id") != extension_id:
        raise HTTPException(409, "Heartbeat required from this extension")
    return {"command": claim_command(extension_id)}


@app.post("/api/bridge/commands/{command_id}/result")
def command_result(command_id: int, payload: CommandResult):
    result = finish_command(command_id, payload.extension_id, payload.status, payload.detail)
    if result != 'ok':
        raise HTTPException(404 if result == 'missing' else 409, "Invalid command or state transition")
    return {"ok": True}


@app.get("/api/events")
def events():
    return {"items": recent_events()}


@app.post("/api/missions")
def missions(payload: MissionCreate):
    mission_id = create_mission(
        market=payload.market,
        mode=payload.mode,
        max_videos=payload.max_videos,
        read_comments=payload.read_comments,
        capture_evidence=payload.capture_evidence,
        discover_related=payload.discover_related,
    )
    log_event(
        "mission",
        f"Mission #{mission_id} created: {payload.mode}, market={payload.market}, max_videos={payload.max_videos}.",
    )
    return {
        "ok": True,
        "mission_id": mission_id,
        "status": "PENDING",
        "note": "Bridge mode foundation is ready; autonomous discovery comes next.",
    }
