"""Connection read model and safe session UX over the existing command queue."""
from datetime import datetime, timezone
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from . import db
from .dev_control import settings,DevCommand,create
from .intelligence_api import local_write

router=APIRouter()


class RecoveryRelease(BaseModel):
    """An explicit human review action from the same-origin connection UI."""
    model_config = ConfigDict(extra='forbid')
    operator_reviewed: Literal[True]


class SearchOnlyRequest(BaseModel):
    """One deliberately requested, bounded search-only collection."""
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=1,max_length=200)


class ViralMissionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    queries: list[str] = Field(min_length=1,max_length=20)


def connection_read_model(bridge: dict, security_stop: dict | None) -> dict:
    """Translate internal bridge facts into the one state shown to normal users.

    The raw bridge/latch values remain available under ``diagnostics`` in the
    endpoint response.  This adapter never changes recovery or safety state.
    """
    security_stop = security_stop or {}
    reason = str(security_stop.get('reason') or '')
    page = str(bridge.get('current_page_status') or 'unknown').lower()
    session = str(bridge.get('tiktok_session_status') or 'unconfirmed').lower()
    connected = bool(bridge.get('connected') and bridge.get('heartbeat_fresh'))
    browser = bool(bridge.get('chrome_connected'))
    tiktok = bool(bridge.get('tiktok_open'))
    blocked_page = page in {'http_403', 'challenge', 'captcha', 'verify', 'verify_human'}
    if reason or blocked_page:
        status, title, message = 'BLOCKED', 'Ação necessária', 'Resolva a verificação manualmente no TikTok e depois clique em Reverificar.'
    elif not connected or not browser:
        status, title, message = 'DISCONNECTED', 'Navegador desconectado', 'A Babi não está recebendo comunicação da extensão.'
    elif not tiktok:
        status, title, message = 'ATTENTION', 'TikTok não encontrado', 'Abra o TikTok no Chrome conectado à Babi.'
    elif session == 'login_required':
        status, title, message = 'ATTENTION', 'Login necessário', 'Faça login manualmente no TikTok. A Babi detectará a sessão automaticamente.'
    elif session != 'confirmed':
        status, title, message = 'ATTENTION', 'Aguardando sessão', 'A Babi está aguardando a confirmação automática da sessão.'
    elif page != 'healthy':
        status, title, message = 'ATTENTION', 'Aguardando TikTok', 'A Babi está aguardando o TikTok terminar de carregar.'
    else:
        status, title, message = 'CONNECTED', 'Conectado', 'Tudo pronto para usar.'
    try:
        seconds = max(0, round((datetime.now(timezone.utc) - datetime.fromisoformat(bridge['last_seen'])).total_seconds()))
    except (KeyError, TypeError, ValueError):
        seconds = None
    return {
        'status': status, 'title': title, 'message': message,
        'browser': 'ONLINE' if browser and connected else 'OFFLINE',
        'tiktok': 'CONNECTED' if tiktok and connected else 'NOT_FOUND',
        'session': 'CONFIRMED' if session == 'confirmed' else ('LOGGED_OUT' if session == 'login_required' else 'UNCONFIRMED'),
        'security': 'BLOCKED' if (reason or blocked_page) else 'OK',
        'mode': 'SEARCH_ONLY', 'lastSeenSeconds': seconds,
    }

@router.get('/api/session/state')
def session_state():
    from .main import live_bridge
    from .companion_contract import contract
    with db.connect() as con:
        renew=con.execute("SELECT id,status,detail,updated_at FROM dev_commands WHERE type='DEV_RENEW_TIKTOK_SESSION' ORDER BY created_at DESC LIMIT 1").fetchone() if con.execute("SELECT 1 FROM sqlite_master WHERE name='dev_commands'").fetchone() else None
        check=con.execute('SELECT id,status,validated_at FROM safe_recovery_checks ORDER BY created_at DESC LIMIT 1').fetchone()
    bridge = live_bridge()
    security_stop = db.get_state('browser_security_stop',{})
    return {**contract(),'connection': connection_read_model(bridge, security_stop),
            'bridge':bridge,'security_stop':security_stop,
            'renewal':dict(renew) if renew else None,'check':dict(check) if check else None}

@router.post('/api/tiktok/renew')
def renew(request:Request):
    local_write(request)
    config=settings()
    from .companion_contract import compatibility
    bridge=db.get_state('tiktok_bridge',{})
    if not compatibility(bridge)['companion_compatible']:raise HTTPException(409,'COMPANION DESATUALIZADO: reload required before session renewal')
    result=create(DevCommand(type='DEV_RENEW_TIKTOK_SESSION',expected_build=bridge['build_id']),config)
    return {**result,'ok':True,'message':'Renovacao solicitada no Chrome existente; security stop preservado; login manual se necessario.'}

@router.post('/api/tiktok/verify')
def verify(request:Request):
    local_write(request)
    config=settings()
    from .safe_collection import request_check
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        return request_check(con,config['extension_id'])


@router.get('/api/tiktok/verify/{ident}')
def verify_result(ident:str):
    """Read one passive recovery check; never changes browser or safety state."""
    with db.connect() as con:
        row=con.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(ident,)).fetchone()
        if not row:raise HTTPException(404,'Unknown verification')
        return dict(row)


@router.post('/api/tiktok/verify/{ident}/release')
def release_verified_latch(ident:str,body:RecoveryRelease,request:Request):
    """Release only a reviewed historical 403 after the matching healthy check."""
    local_write(request)
    config=settings()
    from .safe_collection import release
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        return release(con,ident,config['extension_id'])


@router.post('/api/tiktok/search-only')
def search_only(body:SearchOnlyRequest,request:Request):
    """Use the pinned real TikTok tab through the bounded DiscoveryRunner only."""
    local_write(request)
    config=settings()
    from .discovery_runner import DiscoveryRunner
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        check=con.execute("SELECT id FROM safe_recovery_checks WHERE release_json IS NOT NULL ORDER BY validated_at DESC LIMIT 1").fetchone()
        if not check:raise HTTPException(409,'A released healthy recovery validation is required')
        return DiscoveryRunner.start(con,check['id'],[body.query.strip()],1,allow_explicit_unobserved=True)


@router.post('/api/tiktok/viral-products-72h')
def start_viral_products_72h(body:ViralMissionRequest,request:Request):
    """Explicit temporary mission contract; it expires on mission completion."""
    local_write(request)
    from .viral_products_mission import start
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        return start(con,body.queries)


@router.get('/api/tiktok/viral-products-72h/{ident}')
def viral_products_72h_status(ident:str):
    from .viral_products_mission import report
    with db.connect() as con:
        result=report(con,ident)
        if result is None:raise HTTPException(404,'Unknown Viral Products 72h mission')
        return result
