from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .db import connect, expire_commands
from .schemas import SearchResults
from . import discovery

router=APIRouter()


class DiscoveryStep(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    extension_id: str = Field(min_length=1,max_length=128)
    scroll_iteration: int = Field(ge=0,le=5)
    document_token: str = Field(min_length=1,max_length=128)
    dom_card_count: int = Field(ge=0,le=10000)
    capture: SearchResults
    scroll_target: str | None = Field(default=None,max_length=128)
    scroll_before: float | None = Field(default=None,ge=0)
    scroll_after: float | None = Field(default=None,ge=0)


class DiscoveryFinish(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    extension_id: str = Field(min_length=1,max_length=128)
    stop_reason: Literal['timeout','security_challenge','manual_stop','error']


@router.get('/api/discovery/sessions')
def listing():
    with connect() as con:
        expire_commands(con)
        return {'items':discovery.sessions(con)}


@router.get('/api/discovery/enrichment-queue')
def queue(session_id: int | None=None):
    with connect() as con:
        return {'items':discovery.enrichment_queue(con,session_id)}


@router.get('/api/videos/{video_id}/search-appearances')
def appearances(video_id: str):
    with connect() as con:
        video=con.execute('SELECT * FROM videos WHERE video_id=?',(video_id,)).fetchone()
        if not video:
            raise HTTPException(404,'Library video not found')
        rows=con.execute('''SELECT id,video_id,search_query,search_position,visible_position,
            global_position_estimate,scroll_iteration,capture_id,observed_at FROM search_observations
            WHERE video_id=? ORDER BY observed_at DESC,id DESC LIMIT 100''',(video['id'],)).fetchall()
        return {'first_search_query':video['first_search_query'],'latest_search_query':video['latest_search_query'],
                'total':con.execute('SELECT count(*) FROM search_observations WHERE video_id=?',(video['id'],)).fetchone()[0],
                'items':[dict(row) for row in rows]}


@router.post('/api/discovery/sessions/{session_id}/stop')
def stop(session_id: int):
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        session=con.execute('SELECT * FROM discovery_sessions WHERE id=?',(session_id,)).fetchone()
        if not session:
            raise HTTPException(404,'Discovery session not found')
        discovery.finish(con,dict(session),'manual_stop')
        return {'ok':True}


@router.get('/api/bridge/discovery/{command_id}/control')
def control(command_id: int,extension_id: str):
    with connect() as con:
        return discovery.control(con,command_id,extension_id)


@router.post('/api/bridge/discovery/{command_id}/step')
def step(command_id: int,body: DiscoveryStep):
    if len(body.capture.results)>30:
        raise HTTPException(422,'At most 30 visible results per discovery viewport')
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        return discovery.ingest_step(con,command_id,body.model_dump())


@router.post('/api/bridge/discovery/{command_id}/finish')
def finish(command_id: int,body: DiscoveryFinish):
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        session=discovery.session_for(con,command_id,body.extension_id)
        if session['command_status']!='DISPATCHED' and session['status'] not in discovery.TERMINAL:
            raise HTTPException(409,'Discovery command is not active')
        discovery.finish(con,session,body.stop_reason)
        return discovery.control(con,command_id,body.extension_id)
