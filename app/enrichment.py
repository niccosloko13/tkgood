"""Persistent bounded orchestration of existing semantic readers. No TikTok client."""
import contextvars
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import HTTPException
from . import db

STEPS=('detail','comments','creator','product_detection','corroboration')
worker_context=contextvars.ContextVar('enrichment_worker',default=False)


def config():
    return json.loads((Path(__file__).resolve().parents[1]/'config/enrichment.json').read_text(encoding='utf-8'))


def now():
    return datetime.now(timezone.utc).isoformat()


def migrate(con):
    con.execute('''CREATE TABLE IF NOT EXISTS enrichment_stages (
      video_id INTEGER NOT NULL REFERENCES videos(id),step TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('pending','running','complete','failed','not_applicable')),
      command_id INTEGER,observation_id INTEGER,reason TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL,
      PRIMARY KEY(video_id,step))''')
    con.execute('''CREATE TABLE IF NOT EXISTS enrichment_batches (
      id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,finished_at TEXT,status TEXT NOT NULL,
      stop_requested INTEGER NOT NULL DEFAULT 0,current_video INTEGER,current_step TEXT,
      video_ids_json TEXT NOT NULL,checkpoint_json TEXT NOT NULL DEFAULT '{}',error TEXT)''')
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_active_enrichment ON enrichment_batches((1)) WHERE status='running'")
    if 'broad_concept' not in {r['name'] for r in con.execute('PRAGMA table_info(product_candidates)')}:
        con.execute('ALTER TABLE product_candidates ADD COLUMN broad_concept INTEGER NOT NULL DEFAULT 0')


def active(con):
    return con.execute("SELECT * FROM enrichment_batches WHERE status='running'").fetchone()


def set_stage(con,vid,step,status,reason='',command=None,observation=None):
    con.execute('''INSERT INTO enrichment_stages VALUES (?,?,?,?,?,?,?) ON CONFLICT(video_id,step)
      DO UPDATE SET status=excluded.status,reason=excluded.reason,command_id=COALESCE(excluded.command_id,command_id),
      observation_id=excluded.observation_id,updated_at=excluded.updated_at''',
      (vid,step,status,command,observation,reason,now()))


def valid(con,vid):
    detail=None
    for row in con.execute('SELECT * FROM video_detail_observations WHERE video_id=? ORDER BY id DESC',(vid,)):
        fields=json.loads(row['fields_json'])
        if fields.get('caption') or fields.get('creator_username'):
            detail=row['id'];break
    sample=con.execute('''SELECT s.id FROM comment_samples s WHERE s.video_id=? AND
       (EXISTS(SELECT 1 FROM comment_observations o WHERE o.sample_id=s.id) OR s.stop_reason='no_more_loaded')
       ORDER BY s.id DESC LIMIT 1''',(vid,)).fetchone()
    cutoff=(datetime.now(timezone.utc)-timedelta(hours=config()['creator_reuse_hours'])).isoformat()
    profile=con.execute('''SELECT p.id FROM creator_profile_observations p JOIN video_creators v ON v.creator_id=p.creator_id
       WHERE v.video_id=? AND p.observed_at>=? ORDER BY p.id DESC LIMIT 1''',(vid,cutoff)).fetchone()
    return {'detail':detail,'comments':sample[0] if sample else None,'creator':profile[0] if profile else None}


def queue(con):
    from .discovery import enrichment_queue
    from .creators import link_library
    link_library(con)
    detected={x['video_id']:not x['needs_product_detection'] for x in enrichment_queue(con)}
    from .category_intelligence import library as category_library
    discovery_priorities={v['video_id']:v for v in category_library(con)}
    result=[]
    for video in con.execute('SELECT * FROM videos ORDER BY id').fetchall():
        vid=video['id'];data=valid(con,vid)
        if vid not in detected:
            detection=con.execute('SELECT detected_at FROM product_video_detection_state WHERE video_id=?',(vid,)).fetchone()
            detected[vid]=bool(detection and detection[0]>=video['last_seen_at'])
        previous={r['step']:dict(r) for r in con.execute('SELECT * FROM enrichment_stages WHERE video_id=?',(vid,))}
        states={}
        creator=con.execute('SELECT creator_id FROM video_creators WHERE video_id=?',(vid,)).fetchone()
        for step in STEPS:
            old=previous.get(step,{})
            if data.get(step):
                state='complete';reason='Existing valid observation reused'
            elif step=='creator' and not creator and data['detail']:
                state='not_applicable';reason='No observed creator after detail'
            elif old.get('status') in ('running','failed','not_applicable'):
                state=old['status'];reason=old['reason']
            elif step in ('product_detection','corroboration') and detected.get(vid) and all(data.values()):
                state='complete';reason='Detection already covers available observations'
            elif step in ('product_detection','corroboration') and old.get('status')=='complete' and detected.get(vid):
                state='complete';reason=old['reason']
            else:
                state='pending';reason='Awaiting enrichment'
            states[step]={**old,'status':state,'reason':reason,'observation_id':data.get(step)}
            if old.get('status')!=state or old.get('observation_id')!=data.get(step):
                set_stage(con,vid,step,state,reason,command=old.get('command_id'),observation=data.get(step))
        new=bool(con.execute('SELECT 1 FROM video_enrichment_queue WHERE video_id=?',(vid,)).fetchone())
        useful=bool(video['caption'] and len(video['caption'].strip())>=12)
        hypothesis=bool(con.execute('SELECT 1 FROM product_candidate_evidence WHERE video_id=?',(vid,)).fetchone() or
                        con.execute('SELECT 1 FROM unresolved_product_phrases WHERE video_id=?',(vid,)).fetchone())
        priority=[int(new),int(useful),int(hypothesis),int(not creator)]
        discovery_priority=discovery_priorities.get(vid,{})
        overall='running' if any(s['status']=='running' for s in states.values()) else 'failed' if any(s['status']=='failed' for s in states.values()) else 'pending' if any(s['status']=='pending' for s in states.values()) else 'complete'
        result.append({'video_id':vid,'platform_video_id':video['video_id'],'url':video['canonical_url'],
          'first_seen_at':video['first_seen_at'],
          'caption':video['caption'],'priority':priority,'enrichment_priority':sum(n*(10**(3-i)) for i,n in enumerate(priority)),
          'priority_reason':dict(new_video=new,useful_caption=useful,hypothesis=hypothesis,creator_unknown=not bool(creator)),
          'discovery_enrichment_priority':discovery_priority.get('enrichment_priority',0),
          'discovery_priority_reasons':discovery_priority.get('enrichment_priority_reasons',[]),
          'stages':states,'status':overall})
    def recency(item):
        try:return datetime.fromisoformat(item['first_seen_at']).timestamp()
        except ValueError:return 0
    return sorted(result,key=lambda x:(-x['priority'][0],-x['discovery_enrichment_priority'],*[-n for n in x['priority'][1:]],-recency(x),x['video_id']))


def overview(con):
    from .collection_mode import direct
    items=queue(con)
    batches=[]
    for row in con.execute('SELECT * FROM enrichment_batches ORDER BY id DESC LIMIT 20'):
        b=dict(row);b['video_ids']=json.loads(b.pop('video_ids_json'));b['checkpoint']=json.loads(b.pop('checkpoint_json'));batches.append(b)
    safety=con.execute("SELECT value_json FROM system_state WHERE key='browser_security_stop'").fetchone()
    return {'direct_video_enrichment':direct(con),'items':items,'security_stop':json.loads(safety[0]) if safety else None,'counts':{state:sum(x['status']==state for x in items) for state in ('pending','running','complete','failed')},
      'coverage':{step:sum(x['stages'][step]['status']=='complete' for x in items) for step in STEPS},'total':len(items),'batches':batches,'batch_size':config()['batch_size']}


def diagnose_broad(con):
    from .product_detection import normalize
    heads=set(config()['generic_heads'])
    for row in con.execute('SELECT id,normalized_name FROM product_candidates').fetchall():
        broad=bool(normalize(row['normalized_name']) and set(normalize(row['normalized_name']).split())<=heads)
        con.execute('UPDATE product_candidates SET broad_concept=? WHERE id=?',(int(broad),row['id']))


def create_batch(retry_failed=False):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        from .collection_mode import assert_allowed
        assert_allowed(con)
        if active(con) or db.maintenance_active(con) or con.execute("SELECT 1 FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED')").fetchone():
            raise HTTPException(409,'Wait for active operation')
        row=con.execute("SELECT value_json FROM system_state WHERE key='browser_security_stop'").fetchone()
        if row and json.loads(row[0]).get('reason'):raise HTTPException(409,'Security stop; human review required')
        items=[x for x in queue(con) if x['status']=='pending' or (retry_failed and x['status']=='failed')][:config()['batch_size']]
        if not items:raise HTTPException(409,'No pending videos; failed stages require explicit retry')
        for item in items:
            for step,s in item['stages'].items():
                state='pending' if retry_failed and s['status'] in ('failed','not_applicable') else s['status']
                set_stage(con,item['video_id'],step,state,s['reason'],observation=s.get('observation_id'))
        return con.execute("INSERT INTO enrichment_batches(created_at,status,video_ids_json) VALUES (?,'running',?)",(now(),json.dumps([x['video_id'] for x in items]))).lastrowid


def execute_browser(vid,step):
    from .main import create_command
    from .schemas import VideoDetailCommand
    from .comment_schemas import CommentsCommand
    from .creator_schemas import CreatorCommand
    with db.connect() as con:url=con.execute('SELECT canonical_url FROM videos WHERE id=?',(vid,)).fetchone()[0]
    model={'detail':VideoDetailCommand,'comments':CommentsCommand,'creator':CreatorCommand}[step]
    body={'video_url':url,'type':{'detail':'READ_VIDEO_DETAIL','comments':'READ_COMMENTS_SAMPLE','creator':'READ_CREATOR_PROFILE'}[step]}
    if step=='comments':body['target_count']=config()['comment_target']
    command=create_command(model(**body))
    with db.connect() as con:set_stage(con,vid,step,'running',command=command['id'])
    deadline=time.monotonic()+config()['command_timeout_seconds']
    while time.monotonic()<deadline:
        rows=db.list_commands();result=next((r for r in rows if r['id']==command['id']),None)
        if result and result['status'] in ('SUCCEEDED','FAILED','EXPIRED'):return result
        time.sleep(config()['poll_seconds'])
    raise RuntimeError('Unconfirmed command outcome; stop batch, never repeat browser operation')


def intelligence(con):
    from .product_detection import records
    rows=records(con)
    return dict(candidates=len(rows),observed=sum(x['status']=='observed' for x in rows),corroborated=sum(x['status']=='corroborated' for x in rows),
       cross_video=sum(x['independent_video_count']>1 for x in rows),cross_creator=sum(x['independent_creator_count']>1 for x in rows),
       unresolved=con.execute('SELECT count(*) FROM unresolved_product_phrases').fetchone()[0])


def run_batch(batch_id,reader=execute_browser):
    token=worker_context.set(True);reports=[];processed=[];detection_videos=[];failure=None;status='complete'
    with db.connect() as con:
        ids=json.loads(con.execute('SELECT video_ids_json FROM enrichment_batches WHERE id=?',(batch_id,)).fetchone()[0])
        initial_unresolved=intelligence(con)['unresolved']
        initial_candidates={r[0] for r in con.execute('SELECT id FROM product_candidates')}
    try:
        for vid in ids:
            with db.connect() as con:
                b=con.execute('SELECT * FROM enrichment_batches WHERE id=?',(batch_id,)).fetchone()
                if b['stop_requested']:status='stopped';break
                con.execute('UPDATE enrichment_batches SET current_video=? WHERE id=?',(vid,batch_id))
            processed.append(vid)
            for step in STEPS:
                if db.get_state('browser_security_stop',{}).get('reason'):raise RuntimeError('Security stop; no further navigation')
                with db.connect() as con:
                    item=next(x for x in queue(con) if x['video_id']==vid)
                    stage=item['stages'][step]
                    if stage['status'] in ('complete','not_applicable'):continue
                    con.execute('UPDATE enrichment_batches SET current_step=? WHERE id=?',(step,batch_id))
                    if step=='comments' and not valid(con,vid)['detail']:
                        set_stage(con,vid,step,'not_applicable','Detail unavailable; no comment navigation');continue
                    set_stage(con,vid,step,'running')
                try:
                    if step in ('product_detection','corroboration'):
                        if step=='product_detection':
                            from .product_detection import detect
                            with db.connect() as con:reports.append(detect(con,vid))
                            detection_videos.append(vid)
                        # detect already recalibrates all candidates and relationships atomically.
                        with db.connect() as con:
                            set_stage(con,vid,step,'complete','Existing detector/corroboration pipeline')
                            if step=='product_detection':set_stage(con,vid,'corroboration','complete','Recalculated atomically by detection')
                    else:
                        outcome=reader(vid,step)
                        with db.connect() as con:
                            observation=valid(con,vid)[step]
                            success=outcome['status']=='SUCCEEDED' and observation is not None
                            set_stage(con,vid,step,'complete' if success else 'failed',outcome.get('detail','No valid observation'),command=outcome.get('id'),observation=observation)
                        if 'security' in outcome.get('detail','').lower() or '403' in outcome.get('detail',''):raise RuntimeError('Security stop')
                except HTTPException as error:
                    with db.connect() as con:set_stage(con,vid,step,'failed',str(error.detail))
                except Exception as error:
                    with db.connect() as con:set_stage(con,vid,step,'failed',str(error))
                    raise  # Uncertain transport/database failures must not overlap another command.
    except Exception as error:
        status='failed';failure=str(error)
    finally:
        with db.connect() as con:
            diagnose_broad(con)
            items=[x for x in queue(con) if x['video_id'] in processed]
            current_candidates={r[0] for r in con.execute('SELECT id FROM product_candidates')}
            touched={r[0] for v in detection_videos for r in con.execute('SELECT DISTINCT candidate_id FROM product_candidate_evidence WHERE video_id=?',(v,))}
            checkpoint={'videos_processed':len(processed),**{step+'_complete':sum(x['stages'][step]['status']=='complete' for x in items) for step in ('detail','comments','creator')},
               'failed':sum(x['status']=='failed' for x in items),'new_candidates':len(current_candidates-initial_candidates),
               'updated_candidates':len(touched&initial_candidates),'new_evidence':sum(r['evidence_created'] for r in reports),
               'new_unresolved_phrases':intelligence(con)['unresolved']-initial_unresolved,'intelligence':intelligence(con),'detection_runs':[r['run_id'] for r in reports]}
            con.execute('UPDATE enrichment_batches SET status=?,finished_at=?,checkpoint_json=?,error=? WHERE id=?',(status,now(),json.dumps(checkpoint),failure,batch_id))
        db.log_event('enrichment',f'Batch {batch_id} {status}: '+json.dumps(checkpoint))
        worker_context.reset(token)


def start(retry_failed=False):
    from .main import live_bridge
    bridge=live_bridge()
    if not bridge.get('tiktok_open') or not bridge.get('connected'):raise HTTPException(409,'Companion and existing TikTok tab required')
    batch=create_batch(retry_failed)
    threading.Thread(target=run_batch,args=(batch,),daemon=True,name=f'enrichment-{batch}').start()
    return {'id':batch,'status':'running'}


def recover():
    with db.connect() as con:
        con.execute("UPDATE enrichment_batches SET status='interrupted',finished_at=?,error='Backend restarted; reconcile observations before explicit resume' WHERE status='running'",(now(),))
        con.execute("UPDATE enrichment_stages SET status='failed',reason='Interrupted; verify saved command/observation before retry' WHERE status='running'")
