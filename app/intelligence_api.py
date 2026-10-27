"""Local operational API. No content commands and no network providers."""
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import HTMLResponse,FileResponse
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from .db import connect
from . import intelligence_core as core

router=APIRouter()


def local_write(request):
    # Match origin to the served application; don't expose local work through a third-party page.
    origin=request.headers.get('origin')
    if request.headers.get('sec-fetch-site')=='cross-site' or (origin and origin.rstrip('/')!=str(request.base_url).rstrip('/')):
        raise HTTPException(403,'Same-origin operation required')


@router.get('/api/intelligence-core')
def overview():
    with connect() as con:return core.overview(con)


@router.get('/api/trend-history')
def trend_history(target_type:Literal['VIDEO','PRODUCT_ENTITY','CANDIDATE','CATEGORY','SUBCATEGORY','PRODUCT_FAMILY']='VIDEO',target_id:str|None=None):
    from . import trend_history as trend
    with connect() as con:
        if target_id is None:return trend.overview(con)
        return trend.summarize(trend.snapshots(con,target_type,target_id),target_type)


@router.get('/api/opportunities')
def opportunity_overview():
    """Read-only offline opportunity view; it never queues browser work."""
    from . import trend_engine_v2 as engine
    with connect() as con:
        engine.recompute(con)
        return engine.opportunities(con)


@router.get('/api/opportunities/{candidate_id}')
def opportunity_detail(candidate_id:int):
    from . import trend_engine_v2 as engine
    with connect() as con:
        engine.recompute(con)
        try:
            return engine.candidate_state(con,candidate_id)
        except KeyError:
            raise HTTPException(404,'Candidate not found')


@router.post('/api/intelligence-core/reconcile')
def reconcile(request:Request):
    local_write(request)
    with connect() as con:
        ids=core.enqueue_library(con)
        result=core.process(con)
        return {'jobs':ids,'processed':result}


@router.post('/api/intelligence-core/prepare/{vid}')
def prepare(vid:int,request:Request):
    local_write(request)
    try:
        with connect() as con:
            item=core.observation(con,vid)
            packet=core.visual.prepare_local_assisted(con,vid,item['image'].get('sha256'))
            return {**packet,'caption':item['caption'],'comments':item['comments'],'category':item['category'],'candidates':item['candidates']}
    except (ValueError,KeyError) as exc:raise HTTPException(409,str(exc))


@router.post('/api/intelligence-core/matching-local')
def matching(request:Request):
    local_write(request)
    return core.jobs.start_worker()


@router.post('/api/intelligence-core/visual-start')
def visual_start(request:Request):
    local_write(request)
    return core.jobs.start_worker('visual-identity-worker')


class Review(BaseModel):
    model_config=ConfigDict(extra='forbid')
    human_confirmed:Literal[True]
    action:Literal['confirm','new_product','uncertain']
    name:str|None=Field(default=None,max_length=300)
    product_id:str|None=Field(default=None,max_length=128)
    notes:str=Field(default='',max_length=4000)


@router.post('/api/intelligence-core/review/{did}')
def review(did:int,body:Review,request:Request):
    local_write(request)
    try:
        with connect() as con:return core.review(con,did,body.action,body.name,body.product_id,body.notes)
    except (ValueError,KeyError) as exc:raise HTTPException(409,str(exc))


@router.get('/intelligence-core',response_class=HTMLResponse)
def page():return FileResponse('app/static/intelligence-core.html',media_type='text/html')


@router.get('/assets/intelligence-core.js')
def script():return FileResponse('app/static/intelligence-core.js',media_type='application/javascript')
