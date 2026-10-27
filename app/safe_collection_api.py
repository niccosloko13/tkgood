"""Authenticated explicit recovery operations, separate from content commands."""
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from . import db,safe_collection as safe
from .discovery_runner import DiscoveryRunner
from .dev_control import authorize

router=APIRouter()

class Release(BaseModel):
    model_config=ConfigDict(extra='forbid')
    operator_reviewed:Literal[True]

class Batch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    validation_id:str=Field(pattern=r'^[a-f0-9]{32}$')
    queries:list[str]=Field(min_length=1,max_length=5)
    stage:Literal[1,2]=1

class Stage2Authorization(BaseModel):
    model_config=ConfigDict(extra='forbid')
    validation_id:str=Field(pattern=r'^[a-f0-9]{32}$')
    fresh_check_id:str=Field(pattern=r'^[a-f0-9]{32}$')
    queries:list[str]=Field(min_length=1,max_length=5)
    operator_reviewed:Literal[True]

class Stage2Resume(BaseModel):
    model_config=ConfigDict(extra='forbid')
    fresh_check_id:str=Field(pattern=r'^[a-f0-9]{32}$')
    operator_reviewed:Literal[True]

@router.post('/api/dev/safe-collection/{ident}/resume-stage2')
def resume_stage2(ident:str,body:Stage2Resume,config=Depends(authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        return DiscoveryRunner.resume_stage2(con,ident,body.fresh_check_id,config['extension_id'])

@router.post('/api/dev/safe-collection/authorize-stage2')
def authorize_stage2(body:Stage2Authorization,config=Depends(authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        return DiscoveryRunner.authorize_stage2(con,body.validation_id,body.fresh_check_id,body.queries,config['extension_id'])

@router.post('/api/dev/safe-recovery/checks')
def check(config=Depends(authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE');result=safe.request_check(con,config['extension_id'])
    if result['status'] in ('BLOCKED','CHALLENGE'):
        from .browser_safety import stop
        stop('SAFE_RECOVERY_CHECK '+result['status']+': '+result['evidence']['current_url'],safe.now())
    return result

@router.get('/api/dev/safe-recovery/checks/{ident}')
def check_result(ident:str,config=Depends(authorize)):
    with db.connect() as con:
        row=con.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(ident,)).fetchone()
        if not row:raise HTTPException(404,'Unknown check')
        return dict(row)

@router.post('/api/dev/safe-recovery/checks/{ident}/release')
def release(ident:str,body:Release,config=Depends(authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE');return safe.release(con,ident,config['extension_id'])

@router.post('/api/dev/safe-collection')
def start(body:Batch,config=Depends(authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE');return DiscoveryRunner.start(con,body.validation_id,body.queries,body.stage)


@router.post('/api/dev/safe-recovery/checks/{ident}/authorize-stage1')
def authorize_stage1(ident:str,body:Release,config=Depends(authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE');return safe.authorize_healthy_stage1(con,ident,config['extension_id'])

@router.post('/api/dev/safe-collection/{ident}/next')
def next_query(ident:str,body:Release,config=Depends(authorize)):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE');return DiscoveryRunner.advance(con,ident)

@router.get('/api/collection-health')
def collection_health():
    with db.connect() as con:return safe.summary(con)
