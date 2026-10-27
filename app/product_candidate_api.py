from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .db import connect
from .product_detection import detect, records
from .candidate_corroboration import relationships
from .candidate_gaps import gap_report, unresolved_records, review_phrase
from typing import Literal
from datetime import datetime, timezone

router=APIRouter(prefix='/api/product-candidates')

class DetectionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    video_id: int | None = Field(default=None,gt=0)
    latest_capture: bool = False

class PhraseReview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision: Literal['approved','rejected']
    note: str = Field(default='',max_length=2000)

@router.get('/relationships')
def relationship_list():
    with connect() as con:
        return {'items':relationships(con)}

@router.get('/identity-pairs')
def identity_pairs():
    import json
    with connect() as con:
        return {'items':[{**dict(r),'details':json.loads(r['details_json'])} for r in con.execute("SELECT * FROM product_identity_pairs WHERE pair_key NOT LIKE 'resolver:%' ORDER BY pair_key")]}

@router.get('/resolver-pairs')
def resolver_pairs():
    from .product_identity_resolver import records
    with connect() as con:return {'items':records(con),'score_scale':'0-100 heuristic, not probability','not_merged':True}

@router.get('/resolver-pairs/{pair_id}')
def resolver_pair(pair_id: str):
    from .product_identity_resolver import records
    with connect() as con:
        item=next((p for p in records(con) if p['id']==pair_id),None)
        if item is None:raise HTTPException(404,'Identity pair not found')
        return item

@router.post('/resolve-identity')
def resolve_identity():
    from .product_identity_resolver import resolve
    with connect() as con:return resolve(con)

@router.get('/gap-report')
def gaps():
    with connect() as con:
        return gap_report(con)

@router.get('/unresolved-phrases')
def unresolved():
    with connect() as con:
        return {'items':unresolved_records(con)}

@router.post('/unresolved-phrases/{phrase_id}/review')
def review(phrase_id: int, body: PhraseReview):
    with connect() as con:
        result=review_phrase(con,phrase_id,body.decision,body.note,datetime.now(timezone.utc).isoformat())
        if result is None:
            raise HTTPException(404,'Unresolved phrase not found')
        return result

@router.get('')
def listing():
    with connect() as con:
        return {'items':records(con),'coverage':gap_report(con),'unresolved_phrases':unresolved_records(con)}

@router.post('/detect')
def detection(body: DetectionRequest):
    if body.video_id is not None and body.latest_capture:
        raise HTTPException(422,'Choose video_id or latest_capture')
    with connect() as con:
        if body.video_id is not None and not con.execute('SELECT 1 FROM videos WHERE id=?',(body.video_id,)).fetchone():
            raise HTTPException(404,'Video not found')
        return detect(con,body.video_id,body.latest_capture)

@router.get('/{candidate_id}')
def detail(candidate_id: int):
    with connect() as con:
        items=records(con,candidate_id)
        if not items:
            raise HTTPException(404,'Candidate not found')
        return items[0]
