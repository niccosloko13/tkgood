import os
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from .schemas import BridgeHeartbeat, SearchCommand, CaptureCommand, VideoDetailCommand, CommandResult, RecentVideos, VideoCount, ExtractionQuality, search_page_query
from .db import enqueue_search, enqueue_command, list_commands, claim_command, finish_command, recent_videos, extraction_quality, known_video_url

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
from .schemas import MissionCreate, DiscoveryCommand
from .dev_control import router as dev_router
from .db import maintenance_active
from .comment_schemas import CommentsCommand, CommentsResponse
from .comments import latest_samples
from .db import connect
from .creator_schemas import CreatorCommand, CreatorsResponse
from .creators import creator_for_video, records as creator_records

app = FastAPI(title="Product Hunter — TikTok")
app.include_router(dev_router)
from .safe_collection_api import router as safe_collection_router
app.include_router(safe_collection_router)
from .target_safety import router as target_safety_router
app.include_router(target_safety_router)
from .session_api import router as session_router
app.include_router(session_router)
from .product_candidate_api import router as product_candidate_router
app.include_router(product_candidate_router)
from .discovery_api import router as discovery_router
app.include_router(discovery_router)
from .enrichment_api import router as enrichment_router
app.include_router(enrichment_router)
from .selective_api import router as selective_router
app.include_router(selective_router)
from .manual_captcha_recovery import router as manual_captcha_router
app.include_router(manual_captcha_router)
from .gold_set_api import router as gold_set_router
app.include_router(gold_set_router)
from .category_api import router as category_router
app.include_router(category_router)
from .offline_api import router as offline_router
app.include_router(offline_router)
from .visual_identification_api import router as visual_identification_router
app.include_router(visual_identification_router)
from .intelligence_api import router as intelligence_router
app.include_router(intelligence_router)
from .api_v2 import router as api_v2_router
app.include_router(api_v2_router)
from .api_v2_discovery import router as api_v2_discovery_router
app.include_router(api_v2_discovery_router)
from .api_v2_opportunities import router as api_v2_opportunities_router
app.include_router(api_v2_opportunities_router)
from .api_v2_library import router as api_v2_library_router
app.include_router(api_v2_library_router)
from .api_v2_system import router as api_v2_system_router
app.include_router(api_v2_system_router)
from .api_v2_market_radar import router as api_v2_market_radar_router
app.include_router(api_v2_market_radar_router)

@app.get('/assets/visual-identification.js')
def visual_identification_script():
    from fastapi.responses import FileResponse
    return FileResponse('app/static/visual-identification.js',media_type='application/javascript')

@app.get('/assets/offline-intelligence.js')
def offline_script():
    from fastapi.responses import FileResponse
    return FileResponse('app/static/offline-intelligence.js',media_type='application/javascript')


def live_bridge():
    bridge = get_state("tiktok_bridge", {}) or {}
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(bridge["last_seen"])).total_seconds()
        connected = 0 <= age < 75
    except (KeyError, ValueError, TypeError):
        connected = False
    from .browser_safety import failed_video_url
    latch=get_state('browser_security_stop',{})
    history=get_state('browser_security_history',{}).get('items',[])
    failed=failed_video_url(latch) or next((failed_video_url(x) for x in reversed(history) if failed_video_url(x)),None)
    from .companion_contract import compatibility
    return {**bridge, **compatibility(bridge), "connected": connected,
            "companion_connected": connected, "heartbeat_fresh": connected,
            "security_stop_active":bool(latch.get('reason')), "failed_url":failed,
            "current_page_status": bridge.get('current_page_status','unknown') if connected else 'unknown',
            "tiktok_session_status": bridge.get('tiktok_session_status','unconfirmed') if connected else 'unconfirmed',
            "extension_connected": connected,
            "chrome_connected": connected and bridge.get("chrome_connected", False),
            "tiktok_open": connected and bridge.get("tiktok_open", False),
            "authenticated_hint": connected and bridge.get('tiktok_session_status')=='confirmed'}


@app.on_event("startup")
def startup():
    init_db()
    from .enrichment import recover
    recover()
    from .night_discovery import recover as recover_night
    recover_night()
    from .selective_enrichment import recover as recover_selective
    with connect() as con:recover_selective(con)
    set_state('dev_maintenance', {'enabled': False})
    log_event("system", "Product Hunter TikTok v0.1.4 started (Normal Chrome Bridge mode).")


@app.get("/", response_class=HTMLResponse)
def index():
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get('/assets/category-intelligence.js')
def category_script():
    from fastapi.responses import FileResponse
    return FileResponse('app/static/category-intelligence.js',media_type='application/javascript')


@app.get('/assets/opportunities.js')
def opportunities_script():
    from fastapi.responses import FileResponse
    return FileResponse('app/static/opportunities.js',media_type='application/javascript')


@app.get("/api/status")
def status():
    from .discovery import sessions
    from .enrichment import overview
    with connect() as con:
        discovery_sessions=sessions(con)
        enrichment=overview(con)
    from .companion_contract import contract
    return {
        **contract(),"dev_control_enabled":os.environ.get('PH_DEV_CONTROL')=='1',
        "app": "online",
        "discovery_sessions": discovery_sessions,
        "enrichment":enrichment,
        "mode": "normal_chrome_bridge",
        "security_stop":get_state("browser_security_stop",None),
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
        # Build metadata is optional, so older seven-field heartbeats remain valid.
        "extension_id": x_extension_id,
        "version": payload.extension_version,
        "chrome_connected": True,
        "tiktok_open": payload.current_url.startswith("https://www.tiktok.com/"),
        "connected": True,
        "last_seen": now,
        "url": payload.current_url,
        "tab_id":payload.tab_id,"window_id":payload.window_id,
        "tiktok_tab_count":payload.tiktok_tab_count,"document_visibility":payload.document_visibility,
        "window_state":payload.window_state,"window_width":payload.window_width,
        "window_height":payload.window_height,"tab_active":payload.tab_active,
        "title": payload.page_title,
        "authenticated_hint": payload.authenticated_hint,
        "page_signals": {
            "ready_state": payload.page_ready_state,
            "has_search": payload.has_search_ui,
            "playback_error_visible": payload.playback_error_visible,
            "content_script_connected": payload.page_ready_state is not None,
        },
    }
    from .browser_safety import authenticated_account_evidence
    confirmed=(payload.current_page_status=='healthy' and payload.page_ready_state=='complete' and
               payload.current_url.startswith('https://www.tiktok.com/') and
               payload.tiktok_session_status=='confirmed' and
               authenticated_account_evidence(payload.model_dump()))
    state['authenticated_hint']=confirmed
    if payload.tiktok_session_status=='confirmed' and not confirmed:
        state['tiktok_session_status']='unconfirmed'
    set_state("tiktok_bridge", state)
    from .target_safety import classify_pending,general_block_reason
    general_block=general_block_reason(state)
    if general_block:
        from .browser_safety import stop,failed_video_url
        latch=get_state('browser_security_stop',{})
        if not latch.get('reason') or failed_video_url(latch):stop(general_block,now)
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        target_block=classify_pending(con,state)
    if target_block:
        from .browser_safety import stop
        stop(target_block,now)
    from .safe_collection import observe_heartbeat
    with connect() as con:recovery_block=observe_heartbeat(con,state)
    if recovery_block:
        from .browser_safety import stop
        stop(recovery_block,now)
    if payload.security_stop:
        from .browser_safety import stop
        clearance=get_state('browser_security_clearance',{})
        if not (clearance.get('reason')==payload.security_stop and clearance.get('observed_at')==payload.security_stop_observed_at
                and not get_state('browser_security_stop',{}).get('reason')):
            stop(payload.security_stop,payload.security_stop_observed_at)
    for key in ("extension_id", "chrome_connected", "tiktok_open", "authenticated_hint", "url"):
        if previous.get(key) != state.get(key) or (key == "extension_id" and not previous.get("connected")):
            log_event("bridge", f"Bridge {key}: {state.get(key)}")
    from .companion_contract import contract
    return {**contract(),"dev_control_enabled":os.environ.get('PH_DEV_CONTROL')=='1',"backend_run_id":os.environ.get('PH_RUN_ID'),"ok": True, "received_at": now, "browser_open_request":get_state("browser_open_request",None),"security_stop":get_state("browser_security_stop",None),
            "security_clearance":get_state('browser_security_clearance',None),
            "target_security_pending":bool(get_state('target_security_pending',{}).get('items')),
            "direct_video_enrichment":get_state('direct_video_enrichment',{'status':'ENABLED'}),
            "blocked_targets":blocked_targets_for_worker()}


def blocked_targets_for_worker():
    from .target_safety import rows
    with connect() as con:return rows(con)


@app.get("/api/bridge/state")
def bridge_state():
    return live_bridge()


@app.post("/api/commands", status_code=201)
def create_command(payload: DiscoveryCommand | SearchCommand | CaptureCommand | VideoDetailCommand | CommentsCommand | CreatorCommand):
    from .night_discovery import worker_context as night_context
    with connect() as con:
        if con.execute("SELECT 1 FROM night_discovery_runs WHERE status='running'").fetchone() and not night_context.get():
            raise HTTPException(409,'Night discovery owns the tab; stop the runner first')
    from .enrichment import active,worker_context
    with connect() as con:
        if active(con) and not worker_context.get():
            raise HTTPException(409,'Enrichment batch owns the tab; stop after current video first')
    if maintenance_active():
        raise HTTPException(409, 'Development maintenance in progress')
    if get_state("browser_security_stop",{}).get("reason"):
        raise HTTPException(409,"Browser stopped after security challenge; operator review required")
    bridge = live_bridge()
    if (not bridge["chrome_connected"] or not bridge["tiktok_open"]):
        raise HTTPException(409, "Connect the Companion and open a TikTok tab first")
    if isinstance(payload,DiscoveryCommand):
        try:
            current_query=search_page_query(bridge.get('url',''))
        except ValueError as exc:
            raise HTTPException(409,str(exc))
        if current_query!=payload.query:
            raise HTTPException(409,'Search query must match the visible search page')
        query=payload.query
        command_id=enqueue_command(payload.type,query,bridge['extension_id'],
                                   payload.model_dump(exclude={'type','query'}))
    elif isinstance(payload,CreatorCommand):
        video_url=known_video_url(payload.video_url)
        if video_url is None:
            raise HTTPException(404,'Video must already exist in the captured library')
        with connect() as con:
            creator=creator_for_video(con,video_url)
        if creator is None:
            raise HTTPException(409,'A visible creator username must be collected before reading its profile')
        query=creator['profile_url']
        command_id=enqueue_command(payload.type,query,bridge['extension_id'],{'video_url':video_url})
    elif isinstance(payload, (VideoDetailCommand,CommentsCommand)):
        query = known_video_url(payload.video_url)
        if query is None:
            raise HTTPException(404, 'Video must already exist in the captured library')
        if isinstance(payload,CommentsCommand):
            with connect() as con:
                enriched=con.execute('SELECT 1 FROM video_detail_observations d JOIN videos v ON v.id=d.video_id WHERE v.video_id=?',(query.rsplit('/',1)[1],)).fetchone()
            if not enriched:
                raise HTTPException(409,'Read video detail before sampling comments')
        command_id = enqueue_command(payload.type, query, bridge['extension_id'],
                                     {'target_count':payload.target_count} if isinstance(payload,CommentsCommand) else None)
    elif isinstance(payload, CaptureCommand):
        try:
            query = search_page_query(bridge.get('url', ''))
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        command_id = enqueue_command(payload.type, query, bridge['extension_id'])
    else:
        query = payload.query
        command_id = enqueue_search(query, bridge["extension_id"])
    with connect() as con:
        command_status=con.execute('SELECT status FROM bridge_commands WHERE id=?',(command_id,)).fetchone()[0]
    return {"id": command_id, "type": payload.type, "query": query, "status": command_status}


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
    import re
    with connect() as con:
        owned=con.execute('SELECT * FROM bridge_commands WHERE id=? AND extension_id=?',(command_id,payload.extension_id)).fetchone()
        if not owned:raise HTTPException(404,'Unknown owned command')
        from .target_safety import blocked
        isolated=bool(owned['type'] in ('READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE') and blocked(con,owned['query']) and not re.search(r'captcha|challenge|verify.*human',payload.detail,re.I))
    if not isolated and re.search(r'403|access.denied|captcha|challenge|verify.*human',payload.detail,re.I):
        from .browser_safety import stop
        stop(payload.detail,datetime.now(timezone.utc).isoformat())
    result = finish_command(command_id, payload.extension_id, payload.status, payload.detail,
                            payload.capture.model_dump() if payload.capture is not None else None,
                            payload.video_detail.model_dump() if payload.video_detail is not None else None,
                            payload.comments_sample.model_dump() if payload.comments_sample is not None else None,
                            payload.creator_profile.model_dump() if payload.creator_profile is not None else None,
                            payload.search_diagnostics)
    if result != 'ok':
        raise HTTPException(404 if result == 'missing' else 409, "Invalid command or state transition")
    return {"ok": True}


@app.get('/api/videos/count', response_model=VideoCount)
def video_count():
    return {'total': recent_videos(0)['total']}


@app.get('/api/videos/recent', response_model=RecentVideos)
def videos_recent():
    return recent_videos()


@app.get('/api/extraction/quality', response_model=ExtractionQuality)
def extraction_quality_status():
    return extraction_quality()


@app.get("/api/events")
def events():
    return {"items": recent_events()}


@app.get('/api/comments/summaries',response_model=CommentsResponse)
def comments_summaries():
    with connect() as con:
        return latest_samples(con)


@app.get('/api/creators',response_model=CreatorsResponse)
def creators():
    with connect() as con:
        return creator_records(con)


@app.get('/api/creators/{creator_id}',response_model=CreatorsResponse)
def creator_detail(creator_id: int):
    with connect() as con:
        result=creator_records(con,creator_id)
    if not result['items']:
        raise HTTPException(404,'Creator not found')
    return result


@app.get('/api/videos/{video_id}/comments',response_model=CommentsResponse)
def video_comments(video_id: str):
    if not video_id.isascii() or not video_id.isdigit() or len(video_id)>64:
        raise HTTPException(422,'Expected a numeric video ID')
    with connect() as con:
        return latest_samples(con,video_id,include_comments=True)


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

from .schemas import SecurityStop
@app.post('/api/bridge/security-stop')
def record_security_stop(payload:SecurityStop):
    if live_bridge().get('extension_id')!=payload.extension_id:
        raise HTTPException(403,'Companion identity mismatch')
    from .browser_safety import stop
    return stop(payload.reason,payload.observed_at)
