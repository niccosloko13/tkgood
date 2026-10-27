"""Opt-in, token-protected loopback development control. Never a TikTok action API."""
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from . import db

ROOT = Path(__file__).resolve().parents[1]
router = APIRouter(prefix='/api/dev', dependencies=[])


def settings():
    if os.environ.get('PH_DEV_CONTROL') != '1':
        raise HTTPException(404, 'Development control is disabled')
    try:
        return json.loads((ROOT / '.runtime/dev.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise HTTPException(503, 'Development control is not provisioned')


def authorize(request: Request):
    config = settings()
    if (request.client is None or request.client.host not in ('127.0.0.1', '::1')
            or request.url.hostname not in ('127.0.0.1', 'localhost', '::1')):
        raise HTTPException(403, 'Loopback only')
    origin = request.headers.get('origin')
    if origin and origin != 'chrome-extension://' + config['extension_id']:
        raise HTTPException(403, 'Untrusted origin')
    if not hmac.compare_digest(request.headers.get('x-ph-dev-token', ''), config['token']):
        raise HTTPException(403, 'Invalid development token')
    return config


def extension_authorize(request: Request, config=Depends(authorize)):
    if request.headers.get('x-extension-id') != config['extension_id']:
        raise HTTPException(403, 'Not the provisioned Companion')
    return config


def initialize(con):
    con.execute('''CREATE TABLE IF NOT EXISTS dev_commands (
        id TEXT PRIMARY KEY, type TEXT NOT NULL, status TEXT NOT NULL,
        extension_id TEXT NOT NULL, expected_build TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '', refreshed_tabs INTEGER NOT NULL DEFAULT 0,
        build_id TEXT)''')
    if 'options_json' not in {r[1] for r in con.execute('PRAGMA table_info(dev_commands)')}:
        con.execute("ALTER TABLE dev_commands ADD COLUMN options_json TEXT NOT NULL DEFAULT '{}'")
    if 'result_json' not in {r[1] for r in con.execute('PRAGMA table_info(dev_commands)')}:
        con.execute('ALTER TABLE dev_commands ADD COLUMN result_json TEXT')


def active_operations(con):
    db.expire_commands(con)
    commands = [dict(r) for r in con.execute("SELECT id,type,status FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED')")]
    missions = [dict(r) for r in con.execute("SELECT id,status FROM missions WHERE status IN ('RUNNING','ACTIVE','COLLECTING')")]
    if con.execute("SELECT 1 FROM sqlite_master WHERE name='selective_runs'").fetchone():
        missions.extend({'id':'selective:'+str(r['id']),'status':'RUNNING'} for r in con.execute("SELECT id FROM selective_runs WHERE status='RUNNING'"))
    if con.execute("SELECT 1 FROM sqlite_master WHERE name='enrichment_batches'").fetchone():
        missions.extend({'id':'enrichment:'+str(r['id']),'status':'RUNNING'} for r in con.execute("SELECT id FROM enrichment_batches WHERE status='running'"))
    return {'commands': commands, 'missions': missions}


def maintenance(con, enabled):
    now = datetime.now(timezone.utc)
    value = {'enabled': enabled, 'expires_at': (now + timedelta(minutes=3)).isoformat()}
    con.execute('''INSERT INTO system_state(key,value_json,updated_at) VALUES ('dev_maintenance',?,?)
        ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at''',
        (json.dumps(value), now.isoformat()))


def expire(con):
    initialize(con)
    now = datetime.now(timezone.utc)
    expired_renew=con.execute("SELECT 1 FROM dev_commands WHERE type='DEV_RENEW_TIKTOK_SESSION' AND status IN ('PENDING','ACCEPTED') AND created_at < ?",((now-timedelta(seconds=100)).isoformat(),)).fetchone()
    con.execute("UPDATE dev_commands SET status='EXPIRED',detail='Development operation timed out',updated_at=? WHERE status IN ('PENDING','ACCEPTED') AND created_at < ?",
                (now.isoformat(), (now-timedelta(seconds=100)).isoformat()))
    if expired_renew:maintenance(con,False)


def all_active(con):
    expire(con)
    return {**active_operations(con), 'development': [dict(r) for r in con.execute(
        "SELECT id,type,status FROM dev_commands WHERE status IN ('PENDING','ACCEPTED')")]}


class DevCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    type: Literal['DEV_RELOAD_EXTENSION', 'DEV_REFRESH_TIKTOK','DEV_VALIDATE_TIKTOK_HOME','DEV_RENEW_TIKTOK_SESSION','DEV_INSPECT_TIKTOK_SESSION']
    expected_build: str = Field(pattern=r'^[a-f0-9]{16}$')


class DevCompletion(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['SUCCEEDED', 'FAILED']
    build_id: str = Field(pattern=r'^[a-f0-9]{16}$')
    refreshed_tabs: int = Field(ge=0, le=1000)
    detail: str = Field(max_length=1000)
    session_probe: dict | None = None


@router.post('/recovery/{ident}/clear-reviewed-stop')
def clear_stop(ident: str,config=Depends(authorize)):
    from .browser_safety import clear_reviewed_stop
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        return clear_reviewed_stop(con,ident,config['extension_id'])


@router.get('/status')
def status(config=Depends(authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        expire(con)
        active = all_active(con)
        jobs = [dict(r) for r in con.execute('SELECT * FROM dev_commands ORDER BY created_at DESC LIMIT 10')]
    return {'enabled': True, 'run_id': os.environ.get('PH_RUN_ID'), 'pid': os.getpid(),
            'extension_id': config['extension_id'], 'active': active, 'jobs': jobs}


@router.post('/drain')
def drain(config=Depends(authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        maintenance(con, True)
        active = all_active(con)
    db.log_event('dev', 'Development maintenance requested; waiting for active operations')
    return active


@router.post('/resume')
def resume(config=Depends(authorize)):
    with db.connect() as con:
        maintenance(con, False)
    return {'ok': True}


@router.post('/shutdown')
def shutdown(request: Request, config=Depends(authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        active = all_active(con)
        if any(active.values()):
            raise HTTPException(409, 'Active operation; shutdown refused')
        maintenance(con, True)
    stop = getattr(request.app.state, 'dev_shutdown', None)
    if stop is None:
        raise HTTPException(409, 'Backend not started by the development supervisor')
    db.log_event('dev', 'Supervisor requested graceful backend shutdown')
    stop()
    return {'ok': True, 'run_id': os.environ.get('PH_RUN_ID')}


@router.post('/commands', status_code=201)
def create(payload: DevCommand, config=Depends(authorize)):
    bridge = db.get_state('tiktok_bridge', {}) or {}
    if bridge.get('extension_id') != config['extension_id']:
        raise HTTPException(409, 'Provisioned Companion has not connected')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        expire(con)
        if any(active_operations(con).values()):
            raise HTTPException(409, 'Active operation; dev command refused')
        if con.execute("SELECT 1 FROM dev_commands WHERE status IN ('PENDING','ACCEPTED')").fetchone():
            raise HTTPException(409, 'Another development command is active')
        maintenance(con, True)
        ident, now = secrets.token_hex(16), datetime.now(timezone.utc).isoformat()
        row=con.execute("SELECT value_json FROM system_state WHERE key='browser_security_stop'").fetchone()
        incident=json.loads(row[0]) if row else {}
        if payload.type=='DEV_VALIDATE_TIKTOK_HOME' and incident.get('reason'):
            from .browser_safety import failed_video_url
            if not failed_video_url(incident):
                raise HTTPException(409,'Home recovery requires an isolated historical video HTTP 403; review other challenges manually')
        con.execute("INSERT INTO dev_commands(id,type,status,extension_id,expected_build,created_at,updated_at,options_json) VALUES (?,?,'PENDING',?,?,?,?,?)",
                    (ident, payload.type, config['extension_id'], payload.expected_build, now, now,json.dumps({'incident':incident,'tab_id':bridge.get('tab_id'),'current_url':bridge.get('current_url')})))
    db.log_event('dev', f'{payload.type} {ident} PENDING')
    return {'id': ident, 'status': 'PENDING'}


@router.get('/commands/next')
def next_command(config=Depends(extension_authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        expire(con)
        if any(active_operations(con).values()):
            return {'command': None}
        row = con.execute("SELECT * FROM dev_commands WHERE status='PENDING' AND extension_id=? ORDER BY created_at LIMIT 1", (config['extension_id'],)).fetchone()
    return {'command': dict(row) if row else None}


@router.post('/commands/{ident}/accept')
def accept(ident: str, config=Depends(extension_authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        expire(con)
        row = con.execute('SELECT * FROM dev_commands WHERE id=? AND extension_id=?', (ident, config['extension_id'])).fetchone()
        if not row or row['status'] not in ('PENDING','ACCEPTED'):
            raise HTTPException(409, 'Invalid development command state')
        con.execute("UPDATE dev_commands SET status='ACCEPTED',updated_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), ident))
    db.log_event('dev', f'{row["type"]} {ident} ACCEPTED')
    return {'ok': True}


@router.post('/commands/{ident}/complete')
def complete(ident: str, payload: DevCompletion, config=Depends(extension_authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        expire(con)
        row = con.execute('SELECT * FROM dev_commands WHERE id=? AND extension_id=?', (ident, config['extension_id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Unknown development command')
        if row['status'] == payload.status:
            if all(row[k] == getattr(payload,k) for k in ('build_id','detail','refreshed_tabs')) and (payload.session_probe is None or row['result_json']==json.dumps(payload.session_probe,sort_keys=True)):
                return {'ok': True}
            raise HTTPException(409, 'Changed completion retry')
        if row['status'] != 'ACCEPTED':
            raise HTTPException(409, 'Command was not accepted or has expired')
        if payload.status == 'SUCCEEDED' and payload.build_id != row['expected_build']:
            raise HTTPException(409, 'Loaded extension build does not match requested build')
        if payload.session_probe is not None:
            if row['type']!='DEV_INSPECT_TIKTOK_SESSION' or payload.session_probe.get('mode')!='READ_ONLY_SESSION_PROBE' or payload.session_probe.get('url')!=json.loads(row['options_json']).get('current_url'):
                raise HTTPException(409,'Unexpected session probe or page changed')
            con.execute('UPDATE dev_commands SET result_json=? WHERE id=?',(json.dumps(payload.session_probe,sort_keys=True),ident))
        con.execute('UPDATE dev_commands SET status=?,build_id=?,detail=?,refreshed_tabs=?,updated_at=? WHERE id=?',
                    (payload.status,payload.build_id,payload.detail,payload.refreshed_tabs,datetime.now(timezone.utc).isoformat(),ident))
        if row['type'] in ('DEV_RENEW_TIKTOK_SESSION','DEV_INSPECT_TIKTOK_SESSION'):maintenance(con,False)
    db.log_event('dev', f'{row["type"]} {ident} {payload.status}: {payload.detail}')
    return {'ok': True}
