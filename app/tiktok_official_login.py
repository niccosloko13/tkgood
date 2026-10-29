"""Official TikTok Login Kit for Babi web: no passwords and no browser cookies.

OAuth consent connects identity and permitted APIs, NOT the Chrome collector.
Per-browser httpOnly session cookie; Neon encrypted tokens; state one-time/expiring.
"""
from __future__ import annotations
import base64,hashlib,hmac,json,os,secrets
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest,urlopen
from urllib.error import URLError,HTTPError
from cryptography.fernet import Fernet
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import RedirectResponse
import psycopg

router=APIRouter(prefix="/api/v2/tiktok-connect")
AUTH="https://www.tiktok.com/v2/auth/authorize/"
TOKEN="https://open.tiktokapis.com/v2/oauth/token/"
COOKIE="babi_tt_link"

def settings():
    key=os.environ.get("TIKTOK_CLIENT_KEY","")
    secret=os.environ.get("TIKTOK_CLIENT_SECRET","")
    redirect=os.environ.get("TIKTOK_REDIRECT_URI","")
    encryption=os.environ.get("TIKTOK_OAUTH_ENCRYPTION_KEY","")
    db=os.environ.get("OAUTH_DATABASE_URL","")
    valid=(bool(key and secret and db and redirect.startswith("https://") and encryption))
    return key,secret,redirect,encryption,db,valid

def _db():
    return psycopg.connect(settings()[4])

def _crypto():
    try:return Fernet(settings()[3].encode())
    except (ValueError,TypeError) as exc:raise RuntimeError("Invalid TikTok encryption key") from exc

def migrate():
    with _db() as con,con.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS babi_tiktok_oauth_states(
           state_hash TEXT PRIMARY KEY, session_hash TEXT NOT NULL,
           expires_at TIMESTAMPTZ NOT NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS babi_tiktok_oauth_links(
           session_hash TEXT PRIMARY KEY, open_id_hash TEXT NOT NULL,
           encrypted_tokens BYTEA NOT NULL, scope TEXT NOT NULL,
           expires_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)""")

def _hash(value):return hashlib.sha256(value.encode()).hexdigest()

def _session(req):
    token=req.cookies.get(COOKIE,"")
    return token if len(token)>=32 else None

def _require_config():
    if not settings()[-1]:raise HTTPException(503,"Login TikTok ainda não configurado")

@router.get("/setup-check")
def setup_check(req: Request):
    """Public, non-secret checklist for operator Sandbox readiness."""
    key, secret, redirect, encryption, db, configured = settings()
    encryption_valid = False
    if encryption:
        try:
            Fernet(encryption.encode())
            encryption_valid = True
        except (ValueError, TypeError):
            pass
    return {
        "login_kit_ready": bool(configured and encryption_valid),
        "client_key_set": bool(key),
        "client_secret_set": bool(secret),
        "redirect_uri_set": redirect.startswith("https://"),
        "redirect_host_matches_babi": bool(redirect and redirect.startswith(f"{req.url.scheme}://{req.url.netloc}/")),
        "redirect_uri_is_callback": redirect.endswith("/api/v2/tiktok-connect/callback"),
        "redirect_uri_exact_sandbox": redirect == "https://babi-tiktok-sandbox.vercel.app/api/v2/tiktok-connect/callback",
        "client_key_matches_sandbox": key == "sbawx3z44j9waciu09",
        "encryption_key_valid": encryption_valid,
        "neon_set": bool(db),
        "sandbox_credential_mode": os.environ.get("TIKTOK_LOGIN_ENV", "production") == "sandbox",
        "scope_requested": "user.info.basic",
        "note": "Preview requires its own TikTok Sandbox credentials, Neon URL and callback registered for the same origin. Status only; no secrets."
    }


@router.get("/status")
def status(req:Request):
    enabled=settings()[-1]
    result={"configured":enabled,"connected":False,"scope":None,
            "login_type":"OFFICIAL_TIKTOK_OAUTH","collector_session_shared":False}
    if not enabled or not _session(req):return result
    migrate()
    with _db() as con,con.cursor() as cur:
        cur.execute("SELECT scope,expires_at FROM babi_tiktok_oauth_links WHERE session_hash=%s",
                    (_hash(_session(req)),))
        row=cur.fetchone()
    if row:
        result.update({"connected":True,"scope":row[0],"token_expired":row[1]<=datetime.now(timezone.utc)})
    return result

@router.get("/start")
def start(req:Request):
    _require_config()
    key,_,redirect,_,_,_=settings()
    original=_session(req)
    session=original or secrets.token_urlsafe(40)
    state=secrets.token_urlsafe(40)
    migrate()
    with _db() as con,con.cursor() as cur:
        cur.execute("""INSERT INTO babi_tiktok_oauth_states(state_hash,session_hash,expires_at)
             VALUES(%s,%s,%s)""",(_hash(state),_hash(session),datetime.now(timezone.utc)+timedelta(minutes=10)))
    params={"client_key":key,"response_type":"code","scope":"user.info.basic",
            "redirect_uri":redirect,"state":state}
    response=RedirectResponse(AUTH+"?"+urlencode(params),status_code=302)
    response.set_cookie(COOKIE,session,httponly=True,secure=True,samesite="lax",
                        max_age=60*60*24*30,path="/")
    response.headers["Cache-Control"]="no-store"
    return response

@router.get("/callback")
def callback(req:Request,code:str|None=None,state:str|None=None,error:str|None=None):
    _require_config()
    session=_session(req)
    if error:return RedirectResponse("/?tiktok_connection=denied",status_code=303)
    if not session or not code or not state or len(code)>2048 or len(state)>256:
        raise HTTPException(400,"Autorização inválida")
    migrate()
    # Consume state atomically: one-time use, scoped to browser session.
    with _db() as con,con.cursor() as cur:
        cur.execute("""DELETE FROM babi_tiktok_oauth_states WHERE state_hash=%s
         AND session_hash=%s AND expires_at>now() RETURNING state_hash""",(_hash(state),_hash(session)))
        if not cur.fetchone():raise HTTPException(400,"Autorização expirada ou inválida")
    key,secret,redirect,_,_,_=settings()
    body=urlencode({"client_key":key,"client_secret":secret,"code":code,
                    "grant_type":"authorization_code","redirect_uri":redirect}).encode()
    try:
        with urlopen(UrlRequest(TOKEN,data=body,method="POST",
                               headers={"Content-Type":"application/x-www-form-urlencoded"}),timeout=15) as resp:
            payload=json.load(resp)
    except (HTTPError,URLError,TimeoutError,ValueError) as exc:
        raise HTTPException(502,"TikTok não confirmou a autorização") from exc
    if not isinstance(payload,dict) or not all(payload.get(k) for k in ("access_token","refresh_token","open_id")):
        raise HTTPException(502,"TikTok não retornou uma autorização válida")
    scope=str(payload.get("scope",""))
    if "user.info.basic" not in scope.split(","):
        raise HTTPException(403,"Permissão básica não concedida")
    try: expires=int(payload.get("expires_in",0))
    except (ValueError,TypeError): expires=0
    encrypted=_crypto().encrypt(json.dumps({"access":payload["access_token"],
                                  "refresh":payload["refresh_token"]}).encode())
    with _db() as con,con.cursor() as cur:
        cur.execute("""INSERT INTO babi_tiktok_oauth_links
        (session_hash,open_id_hash,encrypted_tokens,scope,expires_at,updated_at)
        VALUES(%s,%s,%s,%s,%s,now()) ON CONFLICT(session_hash) DO UPDATE
        SET open_id_hash=excluded.open_id_hash,encrypted_tokens=excluded.encrypted_tokens,
        scope=excluded.scope,expires_at=excluded.expires_at,updated_at=now()""",
        (_hash(session),_hash(str(payload["open_id"])),encrypted,scope,
         datetime.now(timezone.utc)+timedelta(seconds=max(expires,0))))
    response=RedirectResponse("/?tiktok_connection=success",status_code=303)
    response.headers["Cache-Control"]="no-store"
    return response

@router.post("/disconnect")
def disconnect(req:Request):
    _require_config()
    session=_session(req)
    if session:
        with _db() as con,con.cursor() as cur:
            cur.execute("DELETE FROM babi_tiktok_oauth_links WHERE session_hash=%s",(_hash(session),))
    response=RedirectResponse("/?tiktok_connection=disconnected",status_code=303)
    response.delete_cookie(COOKIE,path="/")
    response.headers["Cache-Control"]="no-store"
    return response
