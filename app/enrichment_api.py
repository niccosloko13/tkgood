from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,ConfigDict,StrictBool
from . import db,enrichment

router=APIRouter(prefix='/api/enrichment')

class BatchRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    retry_failed:StrictBool=False

@router.get('')
def overview():
    with db.connect() as con:return enrichment.overview(con)

@router.post('/batches',status_code=202)
def start(body:BatchRequest):
    return enrichment.start(body.retry_failed)

@router.post('/batches/{batch_id}/stop')
def stop(batch_id:int):
    with db.connect() as con:
        row=con.execute('SELECT status FROM enrichment_batches WHERE id=?',(batch_id,)).fetchone()
        if not row:raise HTTPException(404,'Batch not found')
        con.execute("UPDATE enrichment_batches SET stop_requested=1 WHERE id=? AND status='running'",(batch_id,))
    return {'stop_after_current_video':True}
