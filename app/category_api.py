from typing import Literal
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from .db import connect
from . import category_intelligence as ci

router=APIRouter(prefix='/api/category-intelligence')

class CategoryReview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    human_reviewed:Literal[True]
    primary_category:str|None=None
    primary_subcategory:str|None=None
    product_family:str|None=Field(default=None,max_length=120)
    notes:str=Field(default='',max_length=4000)

class VisualReview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    human_reviewed:Literal[True]
    image_source:str=Field(min_length=1,max_length=4000)
    provider:Literal['google_lens_assisted','vision_model','web_image_search','supplier_image_search']
    possible_product_name:str|None=Field(default=None,max_length=300)
    result_url:str|None=Field(default=None,max_length=4000)
    confidence:float|None=Field(default=None,ge=0,le=1)
    review_status:Literal['pending','reviewed','rejected']='pending'

@router.get('')
def overview():
    from collections import Counter
    with connect() as con:
        items=ci.library(con);queries=ci.query_metrics(con)
        from .observations import recent
        return {'taxonomy':ci.config(),'items':items,'video_observations':recent(con,-1)['items'],'total':len(items),'queries':queries,'plan':ci.plan(con),
            'distribution':dict(Counter(v['category']['primary_category'] or 'unclassified' for v in items)),
            'subcategories':dict(Counter(v['category']['primary_subcategory'] or 'unclassified' for v in items)),
            'summary':{'videos':len(items),'unique_creators':len({v['creator'] for v in items if v['creator']}),
                'candidates':con.execute('SELECT count(*) FROM product_candidates').fetchone()[0],
                'unresolved':con.execute('SELECT count(*) FROM unresolved_product_phrases').fetchone()[0],
                'unclassified':sum(v['category']['category_status']!='classified' for v in items)},
            'night_runs':[dict(r) for r in con.execute('SELECT * FROM night_discovery_runs ORDER BY id DESC LIMIT 10')]}

@router.get('/library')
def library(category:str|None=None,subcategory:str|None=None,family:str|None=None,creator:str|None=None,
            query:str|None=None,has_product:Literal['yes','no']|None=None,unresolved:Literal['yes','no']|None=None,
            enrichment:str|None=None,candidate_status:str|None=None):
    with connect() as con:
        items=ci.library(con,locals().copy())
        return {'items':items,'total':len(items)}

@router.post('/classify')
def classify():
    with connect() as con:return ci.classify_library(con)

@router.post('/videos/{video_id}/review')
def review(video_id:int,body:CategoryReview):
    with connect() as con:
        try:return ci.review_category(con,video_id,body.model_dump())
        except KeyError as e:raise HTTPException(404,str(e))
        except ValueError as e:raise HTTPException(422,str(e))

@router.get('/videos/{video_id}/history')
def history(video_id:int):
    with connect() as con:
        return {'classifications':[dict(r) for r in con.execute('SELECT * FROM video_category_classifications WHERE video_id=? ORDER BY id',(video_id,))],
            'reviews':[dict(r) for r in con.execute('SELECT * FROM human_category_reviews WHERE video_id=? ORDER BY id',(video_id,))],
            'visual_evidence':[dict(r) for r in con.execute('SELECT * FROM visual_product_evidence WHERE video_id=? ORDER BY id',(video_id,))]}

@router.post('/videos/{video_id}/visual-evidence')
def visual(video_id:int,body:VisualReview):
    from urllib.parse import urlsplit
    if body.result_url and urlsplit(body.result_url).scheme not in ('http','https'):raise HTTPException(422,'Public HTTP(S) reference required')
    with connect() as con:
        if not con.execute('SELECT 1 FROM videos WHERE id=?',(video_id,)).fetchone():raise HTTPException(404,'Video not found')
        con.execute('''INSERT INTO visual_product_evidence(video_id,image_source,provider,possible_product_name,result_url,
            confidence,review_status,observed_at) VALUES (?,?,?,?,?,?,?,?)''',
            (video_id,body.image_source,body.provider,body.possible_product_name,body.result_url,body.confidence,body.review_status,ci.now()))
    return {'saved':True,'product_confirmed':False}

@router.post('/night/start')
def start_night(resume_id:int|None=None):
    from .night_discovery import start
    try:return {'run_id':start(resume_id)}
    except ValueError as e:raise HTTPException(409,str(e))

@router.post('/night/{run_id}/stop')
def stop_night(run_id:int):
    with connect() as con:
        con.execute('UPDATE night_discovery_runs SET stop_requested=1 WHERE id=?',(run_id,))
    return {'stop_requested':True}
