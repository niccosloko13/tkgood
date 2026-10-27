from datetime import datetime,timezone
from typing import Literal
from fastapi import APIRouter,HTTPException,Response,Request
from starlette.concurrency import run_in_threadpool
from urllib.parse import urlsplit
from pydantic import BaseModel,ConfigDict,Field,field_validator
from .db import connect
from . import visual_identification as vi
from . import visual_assets as assets

router=APIRouter(prefix='/api/visual-identification')


def operation(fn,*args):
    try:
        with connect() as con:
            result=fn(con,*args)
            if fn in (vi.suggest,vi.register_image,vi.review_proposal):
                vid=args[0] if fn!=vi.review_proposal else con.execute('SELECT video_id FROM visual_product_evidence WHERE id=?',(args[0],)).fetchone()[0]
                from .intelligence_core import evidence_changed
                evidence_changed(con,vid)
            return result
    except KeyError as e:raise HTTPException(404,str(e))
    except (ValueError,OSError) as e:raise HTTPException(422,str(e))


class LocalImage(BaseModel):
    model_config=ConfigDict(extra='forbid')
    relative_path:str=Field(min_length=1,max_length=1000)
    source_type:Literal['local_frame','local_thumbnail']='local_frame'


class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    human_reviewed:Literal[True]
    review_status:Literal['accepted','rejected','unclear']
    notes:str=Field(default='',max_length=4000)


class ProductSearchEvidence(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title:str=Field(min_length=1,max_length=1000)
    url:str=Field(min_length=1,max_length=4000)
    source:str=Field(min_length=1,max_length=120)
    observed_at:datetime
    possible_match:bool
    match_reason:str=Field(min_length=1,max_length=4000)
    visual_compatible:bool=False
    contradiction:bool=False
    independence_group:str|None=Field(default=None,max_length=120)
    independence_reviewed:bool=False

    @field_validator('url')
    @classmethod
    def url_allowed(cls,value):return vi.public_url(value)

    @field_validator('observed_at')
    @classmethod
    def timezone_required(cls,value):
        if value.utcoffset() is None:raise ValueError('Timezone required')
        return value


class GoldAssessment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    human_reviewed:Literal[True]
    name_match:Literal['exact','acceptable','wrong','unclear']
    helpful:bool|None=None
    notes:str=Field(default='',max_length=4000)


class AssistedStart(BaseModel):
    model_config=ConfigDict(extra='forbid')
    image_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class LensResult(AssistedStart):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    possible_product_name:str=Field(min_length=2,max_length=300)
    result_url:str=Field(min_length=1,max_length=4000)
    source:str=Field(min_length=1,max_length=120)
    listing_title:str=Field(min_length=1,max_length=1000)
    observed_at:datetime
    notes:str=Field(min_length=1,max_length=2000)
    aliases:list[str]=Field(default_factory=list,max_length=12)

    @field_validator('result_url')
    @classmethod
    def reference(cls,value):return vi.public_url(value)

    @field_validator('observed_at')
    @classmethod
    def timestamp(cls,value):
        if value.utcoffset() is None:raise ValueError('Timezone required')
        return value

    @field_validator('aliases')
    @classmethod
    def alias_bounds(cls,values):
        if any(not v.strip() or len(v)>300 for v in values):raise ValueError('Invalid alias')
        return values


@router.get('')
def overview():
    with connect() as con:
        queue=vi.high_queue(con)
        states=vi.provider_states()
        return {'providers':[{'name':k,'mode':'automatic_available' if states.get(k,{}).get('status')=='AVAILABLE_AUTOMATIC' else 'assisted_only',
                             'remote_integration_configured':states.get(k,{}).get('status')=='AVAILABLE_AUTOMATIC'} for k in vi.PROVIDERS],
                'max_visual_items':vi.MAX_VISUAL_ITEMS,'high_queue':[vi.review_item(con,v['video_id'],queue) for v in queue],
                'gold_high_pilot':vi.gold_high_queue(con,queue),'local_asset_metrics':vi.local_asset_metrics(con),
                'metrics':vi.metrics(con)}


@router.get('/videos/{video_id}')
def item(video_id:int):return operation(vi.review_item,video_id)


@router.get('/videos/{video_id}/image')
def image(video_id:int,download:bool=False):
    data,mime=operation(vi.image_bytes,video_id)
    headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
    if download:headers['Content-Disposition']=f'attachment; filename="video-{video_id}.{mime.split("/")[-1]}"'
    return Response(data,media_type=mime,headers=headers)


@router.post('/videos/{video_id}/assets',status_code=201)
async def upload_asset(video_id:int,request:Request,filename:str,source_type:Literal['manual_upload','imported_asset']='manual_upload'):
    # Raw binary upload keeps the stream bounded without adding a multipart parser.
    origin=request.headers.get('origin')
    if origin and origin not in ('http://127.0.0.1:8000','http://localhost:8000'):raise HTTPException(403,'Local upload origin required')
    length=request.headers.get('content-length')
    if length:
        try:
            if int(length)>assets.MAX_BYTES:raise HTTPException(413,'Maximum image size is 10 MiB')
        except ValueError:raise HTTPException(400,'Invalid content length')
    content=bytearray()
    async for chunk in request.stream():
        if len(content)+len(chunk)>assets.MAX_BYTES:raise HTTPException(413,'Maximum image size is 10 MiB')
        content.extend(chunk)
    metadata={'source_type':source_type,'filename':filename,'content_type':request.headers.get('content-type')}
    def store(con):
        result=assets.persist_visual_asset(video_id,bytes(content),metadata,con)
        result['image']=vi.image_source(con,video_id)
        from .intelligence_core import evidence_changed
        evidence_changed(con,video_id)
        return result
    return await run_in_threadpool(operation,store)


@router.post('/videos/{video_id}/assisted-identification')
def prepare(video_id:int,body:AssistedStart):return operation(vi.prepare_assisted,video_id,body.image_sha256)


@router.post('/videos/{video_id}/lens-assisted')
def lens_result(video_id:int,body:LensResult):
    with connect() as con:
        session=con.execute('SELECT 1 FROM visual_assisted_sessions WHERE video_id=? AND image_sha256=?',(video_id,body.image_sha256)).fetchone()
        if not session:raise HTTPException(409,'Prepare the current local image for assisted review first')
        proposal=vi.ProposalInput(provider='google_lens_assisted',possible_product_name=body.possible_product_name,
            aliases=body.aliases,result_url=body.result_url,source_type='assisted_visual_review',observed_at=body.observed_at,
            reason=f'Source: {body.source}\nListing: {body.listing_title}\n{body.notes}',provider_version='lens_manual_v1',image_sha256=body.image_sha256)
        try:record=vi.suggest(con,video_id,proposal)
        except ValueError as exc:raise HTTPException(422,str(exc))
        web=ProductSearchEvidence(title=body.listing_title,url=body.result_url,source=body.source,observed_at=body.observed_at,
            possible_match=False,match_reason=body.notes)
        _save_search(con,record['id'],web)
        return {'evidence_id':record['id'],'review_status':'suggested','product_confirmed':False}


@router.post('/videos/{video_id}/image')
def register(video_id:int,body:LocalImage):return operation(vi.register_image,video_id,body.relative_path,body.source_type)


@router.post('/videos/{video_id}/suggestions')
def suggest(video_id:int,body:vi.ProposalInput):return operation(vi.suggest,video_id,body)


@router.post('/evidence/{evidence_id}/review')
def review(evidence_id:int,body:Decision):return operation(vi.review_proposal,evidence_id,body.review_status,body.notes)


@router.post('/evidence/{evidence_id}/product-search')
def add_search(evidence_id:int,body:ProductSearchEvidence):
    with connect() as con:
        return _save_search(con,evidence_id,body)


def _save_search(con,evidence_id,body):
    if not con.execute('SELECT 1 FROM visual_product_evidence WHERE id=? AND image_sha256 IS NOT NULL',(evidence_id,)).fetchone():
        raise HTTPException(404,'An image-bound visual suggestion is required first')
    if body.independence_reviewed and not body.independence_group:raise HTTPException(422,'Independence group required')
    observed=body.observed_at.astimezone(timezone.utc).isoformat()
    values=(evidence_id,body.title,body.url,body.source,observed,int(body.possible_match),body.match_reason,
            int(body.visual_compatible),int(body.contradiction),body.independence_group,int(body.independence_reviewed))
    old=con.execute('SELECT * FROM visual_product_search_evidence WHERE evidence_id=? AND url=? AND observed_at=?',
                    (evidence_id,body.url,observed)).fetchone()
    keys=('evidence_id','title','url','source','observed_at','possible_match','match_reason','visual_compatible','contradiction','independence_group','independence_reviewed','domain')
    values=(*values,(urlsplit(body.url).hostname or '').lower())
    if old and tuple(old[k] for k in keys)!=values:raise HTTPException(409,'Immutable evidence: changed retry; use a new observation timestamp')
    con.execute('''INSERT OR IGNORE INTO visual_product_search_evidence(evidence_id,title,url,source,observed_at,possible_match,
        match_reason,visual_compatible,contradiction,independence_group,independence_reviewed,domain) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',values)
    from .intelligence_core import evidence_changed
    evidence_changed(con,con.execute('SELECT video_id FROM visual_product_evidence WHERE id=?',(evidence_id,)).fetchone()[0])
    return {'saved':True,'product_confirmed':False,'supplier_listing_created':False}

@router.post('/evidence/{evidence_id}/gold-comparison')
def assess(evidence_id:int,body:GoldAssessment):
    with connect() as con:
        row=con.execute('SELECT * FROM visual_product_evidence WHERE id=? AND image_sha256 IS NOT NULL',(evidence_id,)).fetchone()
        if not row:raise HTTPException(404,'Visual proposal not found')
        reviewed=next((r for r in vi.gold_set.listing(con)['items'] if r['video_id']==row['video_id'] and r['human_reviewed']),None)
        if not reviewed:raise HTTPException(409,'Existing human Gold review required')
        con.execute('INSERT INTO visual_gold_assessments(video_id,evidence_id,name_match,helpful,notes,observed_at,reviewer_type) VALUES (?,?,?,?,?,?,\'human\')',
            (row['video_id'],evidence_id,body.name_match,None if body.helpful is None else int(body.helpful),body.notes,vi.now()))
    return {'saved':True,'gold_set_changed':False}
