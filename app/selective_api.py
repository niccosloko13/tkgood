from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import FileResponse
from . import db,selective_enrichment as selective
from .intelligence_api import local_write
from . import collection_mode,search_intelligence

router=APIRouter()


@router.get('/api/selective-enrichment')
def overview():
    with db.connect() as c:
        mode=collection_mode.status(c)
        if mode['direct_video_enrichment']['status']=='PAUSED':
            batch=c.execute("SELECT id FROM safe_collection_batches WHERE stage=2 AND status='SUCCEEDED' ORDER BY created_at DESC LIMIT 1").fetchone()
            ids=[r[0] for r in c.execute("SELECT DISTINCT o.video_id FROM search_observations o JOIN safe_query_metrics m ON o.capture_id='command:'||m.command_id WHERE m.batch_id=?",(batch['id'],))] if batch else [r[0] for r in c.execute('SELECT DISTINCT video_id FROM search_observations')]
            items=[];index=search_intelligence._creator_index(c)
            for vid in ids:
                signals=search_intelligence.analyze(c,vid,index)
                if not signals:continue
                items.append({'video_id':vid,'platform_video_id':signals['video_url'].rsplit('/',1)[-1] if signals['video_url'] else str(vid),'video_url':signals['video_url'],'caption':signals['caption'],'creator':signals['creator'],'priority':signals['priority'],'why':signals['why'],'features':signals,'current_intelligence':signals['dimensions'],'search_intelligence':signals,'enrichment_status':'DIRECT_ENRICHMENT_PAUSED','enrichment_availability':'SEARCH_ONLY','comments_availability':'UNAVAILABLE_SEARCH_ONLY','creator_detail_availability':'UNAVAILABLE_SEARCH_ONLY'})
            order={'HIGH':0,'MEDIUM':1,'LOW':2,'INSUFFICIENT':3};items.sort(key=lambda x:(order[x['priority']],-x['search_intelligence']['query_diversity'],x['video_id']))
        else:
            items=selective.candidates(c)
            for item in items[:12]:item['current_intelligence']=selective.intelligence(c,item['video_id'])
        latest=c.execute('SELECT id FROM selective_runs ORDER BY id DESC LIMIT 1').fetchone()
        contexts=collection_mode.history(c)
    return {'version':selective.VERSION,'operational':mode,'challenge_history':contexts,'limit':selective.LIMIT,'items':items,'counts':{bucket:sum(x['priority']==bucket for x in items) for bucket in ('HIGH','MEDIUM','LOW','INSUFFICIENT')},'last_run':selective.report(latest['id']) if latest else None}


@router.post('/api/selective-enrichment/start',status_code=202)
def start(request:Request):
    local_write(request)
    with db.connect() as c:
        collection_mode.assert_allowed(c)
        if c.execute('SELECT 1 FROM selective_runs').fetchone():raise HTTPException(409,'Pilot already exists; no automatic repeat')
    from scripts.background_runner import launch
    return {'task_id':launch('selective-enrichment',[])}


@router.post('/api/selective-enrichment/{ident}/stop')
def stop(ident:int,request:Request):
    local_write(request)
    with db.connect() as c:c.execute("UPDATE selective_runs SET stop_requested=1 WHERE id=? AND status='RUNNING'",(ident,))
    return {'stop_requested':True}


@router.get('/assets/selective-enrichment.js')
def script():return FileResponse('app/static/selective-enrichment.js',media_type='application/javascript')

@router.get('/api/search-only-intelligence')
def search_only():
    with db.connect() as c:
        index=search_intelligence._creator_index(c)
        return {'version':search_intelligence.VERSION,'operational':collection_mode.status(c),'items':[search_intelligence.analyze(c,r[0],index) for r in c.execute('SELECT DISTINCT video_id FROM search_observations').fetchall()]}
