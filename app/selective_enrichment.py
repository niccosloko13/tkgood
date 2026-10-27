"""Selective scheduling and bounded semantic readers. No opportunity score or AI.

Priority uses persisted pre-enrichment facts, frozen before any browser operation.
Only selected items receive identity/dimension recomputation; no global job drain.
"""
import contextvars
import hashlib
import json
import re
import time
from datetime import datetime,timezone,timedelta
from fastapi import HTTPException
from . import db,safe_collection as safe,target_safety

VERSION='selective-enrichment-v1'
LIMIT=5
RUNTIME=600
CONTEXT=contextvars.ContextVar('selective_worker',default=False)
TYPES={'detail':'READ_VIDEO_DETAIL','comments':'READ_COMMENTS_SAMPLE','creator':'READ_CREATOR_PROFILE'}


def now():return datetime.now(timezone.utc).isoformat()
def encode(v):return json.dumps(v,sort_keys=True,ensure_ascii=False)


def migrate(c):
    c.execute('''CREATE TABLE IF NOT EXISTS selective_runs (
      id INTEGER PRIMARY KEY,pilot_key TEXT NOT NULL UNIQUE,status TEXT NOT NULL,
      created_at TEXT NOT NULL,finished_at TEXT,deadline_at TEXT NOT NULL,
      current_video INTEGER,current_step TEXT,stop_requested INTEGER NOT NULL DEFAULT 0,
      selected_json TEXT NOT NULL,stop_reason TEXT,checkpoint_json TEXT NOT NULL DEFAULT '{}')''')
    c.execute('''CREATE TABLE IF NOT EXISTS selective_items (
      run_id INTEGER NOT NULL,video_id INTEGER NOT NULL,priority_json TEXT NOT NULL,
      before_json TEXT NOT NULL,after_json TEXT,status TEXT NOT NULL,steps_json TEXT NOT NULL,
      PRIMARY KEY(run_id,video_id))''')
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_selective_active ON selective_runs((1)) WHERE status='RUNNING'")


def active(c):return c.execute("SELECT * FROM selective_runs WHERE status='RUNNING'").fetchone()


def _recent(stamp,hours):
    try:return timedelta(0)<=datetime.now(timezone.utc)-datetime.fromisoformat(stamp.replace('Z','+00:00'))<timedelta(hours=hours)
    except (TypeError,ValueError,AttributeError):return False


def intelligence(c,vid,recompute=False):
    from . import intelligence_core as core,intelligence_signals as sig
    identity=c.execute('SELECT * FROM intelligence_decisions WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
    if recompute:
        identity=core.identify(c,vid,with_embeddings=False)
    status=identity['status'] if identity else 'UNRESOLVED'
    result=sig.for_video(c,vid,status)
    if recompute:sig.persist(c,vid,result)
    dims={k:{'status':v['status'],'classification':v.get('classification'),'sample_size':v.get('sample_size'),'evidence_ids':v.get('evidence_ids',[])} for k,v in result['dimensions'].items() if k in ('purchase_intent','signal_quality','product_quality','creative_dna','trend_readiness','commercial_readiness')}
    profile=c.execute('''SELECT p.* FROM creator_profile_observations p WHERE p.creator_id IN
      (SELECT creator_id FROM video_creators WHERE video_id=? UNION SELECT c.creator_id FROM creators c JOIN videos v ON lower(v.creator_username)=lower(c.username) WHERE v.id=?) ORDER BY p.id DESC LIMIT 1''',(vid,vid)).fetchone()
    measured=profile and any(profile[k] is not None for k in ('followers','following','total_likes','video_count'))
    dims['creator_signal']={'status':'measured' if measured else 'partial' if profile else 'insufficient_data','evidence_ids':[f"creator_profile:{profile['id']}"] if profile else [],'followers':profile['followers'] if profile else None,'observed_at':profile['observed_at'] if profile else None}
    return {'identity':{'status':status,'decision_id':identity['id'] if identity else None},**dims}


def candidates(c):
    from .product_detection import extractProductCandidatePhrases
    from .intelligence_decisions import specificity
    from .comments import consumer_signals_v2
    from .trend_history import for_video
    batch=c.execute("SELECT id FROM safe_collection_batches WHERE stage=2 AND status='SUCCEEDED' ORDER BY created_at DESC LIMIT 1").fetchone()
    scoped={r[0] for r in c.execute("SELECT DISTINCT o.video_id FROM search_observations o JOIN safe_query_metrics m ON o.capture_id='command:'||m.command_id WHERE m.batch_id=?",(batch['id'],))} if batch else {r[0] for r in c.execute('SELECT DISTINCT video_id FROM search_observations')}
    output=[]
    for v in c.execute('SELECT * FROM videos ORDER BY id'):
        if v['id'] not in scoped:continue
        vid=v['id'];observations=[dict(r) for r in c.execute('SELECT * FROM search_observations WHERE video_id=? ORDER BY observed_at,id',(vid,))]
        comments=[dict(r) for r in c.execute('SELECT * FROM comment_observations WHERE video_id=?',(vid,))]
        phrases=[r[0] for r in c.execute('SELECT DISTINCT p.canonical_name FROM product_candidates p JOIN product_candidate_evidence e ON e.candidate_id=p.id WHERE e.video_id=?',(vid,))]
        phrases+= [p['raw_phrase'] for p in extractProductCandidatePhrases(v['caption'] or '')]
        specific=sorted({p for p in phrases if specificity(p,v['caption'] or '',comments)['specific']})
        peers={r[0] for r in c.execute('SELECT DISTINCT e2.video_id FROM product_candidate_evidence e JOIN product_candidate_evidence e2 ON e.candidate_id=e2.candidate_id WHERE e.video_id=?',(vid,))}
        known_creators={r[0].lower() for r in c.execute('SELECT creator_username FROM videos WHERE id IN (SELECT DISTINCT e2.video_id FROM product_candidate_evidence e JOIN product_candidate_evidence e2 ON e.candidate_id=e2.candidate_id WHERE e.video_id=?) AND creator_username IS NOT NULL',(vid,))}
        latest={}
        for row in observations:latest.update({k:val for k,val in json.loads(row['fields_json']).items() if val is not None})
        for row in c.execute('SELECT fields_json FROM video_detail_observations WHERE video_id=? ORDER BY observed_at,id',(vid,)):latest.update({k:val for k,val in json.loads(row[0]).items() if val is not None})
        numeric={k:latest.get(k) if isinstance(latest.get(k),(int,float)) and not isinstance(latest.get(k),bool) else None for k in ('views','likes','comments_count','shares','favorites')}
        engagement=any(numeric[k] is not None for k in ('likes','comments_count','shares','favorites'))
        queries=sorted({o['search_query'] for o in observations});captures=len({o['capture_id'] for o in observations})
        category=c.execute('SELECT primary_category,category_status FROM video_category_classifications WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
        relevant=bool(category and category['primary_category']=='home')
        intent=consumer_signals_v2(comments);trend=for_video(c,vid)
        new=_recent(v['first_seen_at'],48);density=(captures-len(queries))/captures if captures else None
        blocked=target_safety.blocked(c,v['canonical_url'])
        reasons=[]
        if specific:reasons.append('SPECIFIC_LITERAL_PRODUCT: '+', '.join(specific[:3]))
        if len(queries)>=2:reasons.append(f'QUERY_DIVERSITY: {len(queries)}')
        if captures>=2:reasons.append(f'RECAPTURES: {captures}; local recurrence, not independent products')
        if new:reasons.append('FIRST_OBSERVED_WITHIN_48H')
        if relevant:reasons.append('PERSISTED_HOME_CATEGORY')
        if len(known_creators)>1:reasons.append(f'UNCONFIRMED_CANDIDATE_CREATOR_COVERAGE: {len(known_creators)}')
        if intent['intent_comments']:reasons.append('EXISTING_PURCHASE_INTENT')
        if (numeric['views'] or 0)>=10000:reasons.append('VISIBLE_VIEWS_AT_LEAST_10000')
        if engagement:reasons.append('PERSISTED_ENGAGEMENT_METRICS_AVAILABLE')
        history_ready=trend['quality'].get('strength') not in (None,'insufficient','insufficient_data')
        if history_ready:reasons.append('LOCAL_TEMPORAL_COVERAGE_AVAILABLE; not a forecast')
        if density is not None and density>.8:reasons.append('HIGH_REPEAT_DENSITY; repeated captures are not independent corroboration')
        support=relevant or len(queries)>=2 or new or intent['intent_comments']>0 or (numeric['views'] or 0)>=10000 or engagement or len(known_creators)>1 or history_ready
        if blocked:bucket='LOW';reasons=['TARGET_PREVIOUSLY_BLOCKED']
        elif not v['caption'] or not v['creator_username']:bucket='INSUFFICIENT';reasons.append('CAPTION_OR_OBSERVED_CREATOR_MISSING')
        elif specific and support and not (density is not None and density>.8 and len(queries)==1 and not new and not intent['intent_comments']):bucket='HIGH'
        elif specific or len(queries)>=2 or relevant:bucket='MEDIUM'
        elif len((v['caption'] or '').split())<4:bucket='INSUFFICIENT';reasons.append('NO_SPECIFIC_PRODUCT_OR_SUFFICIENT_CONTEXT')
        else:bucket='LOW';reasons.append('NO_SPECIFIC_PRODUCT_SUPPORT')
        features={'novelty':new,'recurrence':captures,'query_diversity':len(queries),'queries':queries,'known_candidate_videos':len(peers),'known_candidate_creators':len(known_creators),'metrics':numeric,'metrics_basis':'most recent nonnull historical persisted value; not assumed current','engagement_available':engagement,'existing_purchase_intent':intent['strength'],'intent_evidence_ids':intent['evidence_ids'],'category_relevant':relevant,'specificity':specific,'lifecycle':trend['lifecycle'],'trend_observations':trend['observations'],'trend_quality':trend['quality'],'duplicate_density':density,'search_evidence_ids':[o['id'] for o in observations],'detail_evidence_ids':[o[0] for o in c.execute('SELECT id FROM video_detail_observations WHERE video_id=?',(vid,))]}
        last=c.execute('SELECT status,run_id FROM selective_items WHERE video_id=? ORDER BY run_id DESC LIMIT 1',(vid,)).fetchone()
        output.append({'video_id':vid,'platform_video_id':v['video_id'],'video_url':v['canonical_url'],'caption':v['caption'],'creator':v['creator_username'],'priority':bucket,'why':reasons,'features':features,'enrichment_status':last['status'] if last else 'NOT_SELECTED'})
    # Scheduling tuple only; never a product/opportunity score. Prefer evidence
    # diversity then novelty; ID is the final deterministic tie break.
    order={'HIGH':0,'MEDIUM':1,'LOW':2,'INSUFFICIENT':3}
    return sorted(output,key=lambda x:(order[x['priority']],-x['features']['query_diversity'],-int(x['features']['novelty']),x['video_id']))


def permitted(c,run,kind,query,options):
    from .collection_mode import direct
    if direct(c)['status']=='PAUSED':return False
    if not run or run['status']!='RUNNING' or run['stop_requested'] or datetime.now(timezone.utc)>=datetime.fromisoformat(run['deadline_at']):return False
    if kind!=TYPES.get(run['current_step']):return False
    item=c.execute('SELECT * FROM selective_items WHERE run_id=? AND video_id=?',(run['id'],run['current_video'])).fetchone()
    video=c.execute('SELECT * FROM videos WHERE id=?',(run['current_video'],)).fetchone()
    if not item or not video or item['status']!='RUNNING':return False
    if target_safety.blocked(c,video['canonical_url']) or target_safety.blocked(c,query):return False
    if kind=='READ_CREATOR_PROFILE':return bool(video['creator_username'] and query.lower()=='https://www.tiktok.com/'+video['creator_username'].lower() and (options or {}).get('video_url')==video['canonical_url'])
    return query==video['canonical_url']


def command_allowed(c,row):
    options=json.loads(row['options_json']);ident=options.get('selective_run_id')
    if not ident:return False
    run=c.execute('SELECT * FROM selective_runs WHERE id=?',(ident,)).fetchone()
    return permitted(c,run,row['type'],row['query'],options)


def _guard(c,allow_video=True):
    from .collection_mode import assert_allowed
    assert_allowed(c)
    b=safe.state(c,'tiktok_bridge')
    if safe.state(c,'browser_security_stop').get('reason'):raise RuntimeError('GLOBAL_SECURITY_EVENT')
    if safe.state(c,'target_security_pending').get('items'):raise RuntimeError('TARGET_HEALTH_PENDING')
    if b.get('current_page_status')!='healthy' or b.get('tiktok_session_status')!='confirmed' or b.get('page_ready_state')!='complete':raise RuntimeError('SESSION_OR_PAGE_NOT_STABLE')
    try:fresh=0<=(datetime.now(timezone.utc)-datetime.fromisoformat(b['last_seen'])).total_seconds()<15
    except (KeyError,ValueError):fresh=False
    if not fresh:raise RuntimeError('COMPANION_NOT_FRESH')
    if not allow_video and not safe.healthy_route(b.get('current_url','')):raise RuntimeError('HEALTHY_HOME_SEARCH_REQUIRED')


def unselected_digest(c,selected):
    tables=('intelligence_decisions','intelligence_dimension_snapshots','intelligence_matches','intelligence_entity_observations','video_detail_observations','comment_samples','comment_observations')
    data={}
    for table in tables:
        exists=c.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone()
        data[table]=[dict(r) for r in c.execute(f'SELECT * FROM {table} ORDER BY rowid') if r['video_id'] not in selected] if exists else []
    return hashlib.sha256(encode(data).encode()).hexdigest()


def create(pilot_key='selective-v1-20261025'):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE');migrate(c)
        if c.execute('SELECT 1 FROM selective_runs WHERE pilot_key=?',(pilot_key,)).fetchone():raise HTTPException(409,'Pilot already started; no automatic repeat')
        from .dev_control import active_operations
        if active(c) or db.maintenance_active(c) or any(active_operations(c).values()):raise HTTPException(409,'Another operation owns the tab')
        _guard(c,False)
        selected=[x for x in candidates(c) if x['priority']=='HIGH' and x['enrichment_status'] not in ('ENRICHED','RUNNING')][:LIMIT]
        if not selected:raise HTTPException(409,'NO_HIGH_CANDIDATES')
        stamp=now();deadline=(datetime.now(timezone.utc)+timedelta(seconds=RUNTIME)).isoformat()
        ident=c.execute("INSERT INTO selective_runs(pilot_key,status,created_at,deadline_at,selected_json) VALUES (?,'RUNNING',?,?,?)",(pilot_key,stamp,deadline,encode([x['video_id'] for x in selected]))).lastrowid
        for item in selected:c.execute("INSERT INTO selective_items VALUES (?,?,?,?,NULL,'SELECTED','{}')",(ident,item['video_id'],encode(item),encode(intelligence(c,item['video_id']))))
        checkpoint={'unselected_digest_before':unselected_digest(c,[x['video_id'] for x in selected]),'scope':'latest completed Stage 2 batch; local library evidence may support priority','priority_version':VERSION}
        c.execute('UPDATE selective_runs SET checkpoint_json=? WHERE id=?',(encode(checkpoint),ident))
        return ident


def _save_item(c,run_id,vid,status,steps,after=None):
    c.execute('UPDATE selective_items SET status=?,steps_json=?,after_json=coalesce(?,after_json) WHERE run_id=? AND video_id=?',(status,encode(steps),encode(after) if after is not None else None,run_id,vid))


def recent(c,vid,step):
    if step=='detail':row=c.execute('SELECT * FROM video_detail_observations WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
    elif step=='comments':row=c.execute('SELECT * FROM comment_samples WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
    else:row=c.execute('SELECT p.* FROM creator_profile_observations p JOIN video_creators v ON p.creator_id=v.creator_id WHERE v.video_id=? ORDER BY p.id DESC LIMIT 1',(vid,)).fetchone()
    return row if row and _recent(row['observed_at'],168 if step=='creator' else 24) else None


def run(ident,reader=None):
    from .enrichment import execute_browser,worker_context
    reader=reader or execute_browser;token=CONTEXT.set(True);legacy=worker_context.set(True);reason='PILOT_LIMIT';status='COMPLETED'
    try:
        with db.connect() as c:
            initial=c.execute('SELECT * FROM selective_runs WHERE id=?',(ident,)).fetchone()
            ids=json.loads(initial['selected_json']);checkpoint=json.loads(initial['checkpoint_json'])
        single=checkpoint.get('max_candidates')==1
        if single:
            from .manual_captcha_recovery import checkpoint as passive_checkpoint
            checkpoint['pre_check']=passive_checkpoint(ids[0],'pre',initial['created_at'])
            with db.connect() as c:c.execute('UPDATE selective_runs SET checkpoint_json=? WHERE id=?',(encode(checkpoint),ident))
            reason='SINGLE_CANDIDATE_LIMIT'
        elif len(ids)<LIMIT:reason='NO_MORE_HIGH'
        for vid in ids:
            steps={};item_status='ENRICHED'
            with db.connect() as c:
                record=c.execute('SELECT * FROM selective_runs WHERE id=?',(ident,)).fetchone()
                if record['stop_requested']:reason='OPERATOR_STOP';status='STOPPED';break
                if target_safety.blocked(c,c.execute('SELECT canonical_url FROM videos WHERE id=?',(vid,)).fetchone()[0]):_save_item(c,ident,vid,'BLOCKED',{'skip':'TARGET_PREVIOUSLY_BLOCKED'});continue
                _guard(c)
                c.execute("UPDATE selective_runs SET current_video=? WHERE id=?",(vid,ident));_save_item(c,ident,vid,'RUNNING',steps)
            for step in TYPES:
                with db.connect() as c:
                    record=c.execute('SELECT * FROM selective_runs WHERE id=?',(ident,)).fetchone()
                    if record['status']!='RUNNING':raise RuntimeError('RUN_NOT_ACTIVE')
                    remaining=(datetime.fromisoformat(record['deadline_at'])-datetime.now(timezone.utc)).total_seconds()
                    if remaining<(95 if step=='comments' else 45):raise RuntimeError('MAX_RUNTIME')
                    video=c.execute('SELECT * FROM videos WHERE id=?',(vid,)).fetchone()
                    if target_safety.blocked(c,video['canonical_url']):item_status='BLOCKED';steps[step]={'status':'SKIPPED','reason':'TARGET_PREVIOUSLY_BLOCKED'};break
                    _guard(c)
                    if step=='creator' and video['creator_username']:
                        from .creators import creator_for_video
                        creator_for_video(c,video['canonical_url'])
                    reuse=recent(c,vid,step)
                    if reuse:steps[step]={'status':'REUSED','observation_id':reuse['id'],'observed_at':reuse['observed_at'],'post_check':{'status':'NO_BROWSER_ACTION','basis':'saved observation reused'}};_save_item(c,ident,vid,'RUNNING',steps);continue
                    if step=='comments' and not recent(c,vid,'detail'):steps[step]={'status':'SKIPPED','reason':'DETAIL_UNAVAILABLE'};item_status='PARTIAL';continue
                    if step=='creator' and not video['creator_username']:steps[step]={'status':'SKIPPED','reason':'OBSERVED_CREATOR_UNAVAILABLE'};item_status='PARTIAL';continue
                    profile='https://www.tiktok.com/'+video['creator_username'] if video['creator_username'] else ''
                    if step=='creator' and target_safety.blocked(c,profile):steps[step]={'status':'SKIPPED','reason':'TARGET_PREVIOUSLY_BLOCKED'};item_status='PARTIAL';continue
                    c.execute('UPDATE selective_runs SET current_step=? WHERE id=?',(step,ident))
                outcome=reader(vid,step)
                with db.connect() as c:
                    blocked=target_safety.blocked(c,video['canonical_url']) or (step=='creator' and target_safety.blocked(c,profile))
                    if blocked:steps[step]={'status':'BLOCKED','command_id':outcome.get('id'),'reason':'TARGET_HTTP_403'};item_status='BLOCKED';_save_item(c,ident,vid,item_status,steps);break
                    observed=recent(c,vid,step)
                    success=outcome['status']=='SUCCEEDED' and observed is not None
                    steps[step]={'status':'COLLECTED' if success else 'FAILED','command_id':outcome.get('id'),'observation_id':observed['id'] if success else None,'reason':outcome.get('detail','')}
                    if not success:item_status='PARTIAL'
                    _save_item(c,ident,vid,'RUNNING',steps)
                    global_stopped=bool(safe.state(c,'browser_security_stop').get('reason'))
                if global_stopped:raise RuntimeError('GLOBAL_SECURITY_EVENT')
                if outcome['status']=='EXPIRED':raise RuntimeError('COMMAND_EXPIRED_NO_RETRY')
                if single:
                    with db.connect() as c:
                        sent=c.execute('SELECT updated_at FROM bridge_commands WHERE id=?',(outcome.get('id'),)).fetchone()
                    try:steps[step]['post_check']=passive_checkpoint(vid,step,sent['updated_at'] if sent else now())
                    except RuntimeError as error:
                        steps[step]['post_check']={'status':'BLOCKED','reason':str(error),'samples':getattr(error,'samples',[])}
                        with db.connect() as c:_save_item(c,ident,vid,'RUNNING',steps)
                        raise
                    with db.connect() as c:_save_item(c,ident,vid,'RUNNING',steps)
                    continue
                # Allow a completed navigation's next passive heartbeat to arrive;
                # no page operation is retried or manufactured to obtain health.
                deadline=time.monotonic()+25
                while True:
                    try:
                        with db.connect() as c:_guard(c)
                        break
                    except RuntimeError as error:
                        if str(error) not in ('SESSION_OR_PAGE_NOT_STABLE','COMPANION_NOT_FRESH') or time.monotonic()>=deadline:raise
                    time.sleep(1)
            with db.connect() as c:
                after=intelligence(c,vid,recompute=any(v.get('status')=='COLLECTED' for v in steps.values() if isinstance(v,dict))) if item_status!='BLOCKED' else None
                _save_item(c,ident,vid,item_status,steps,after)
            if item_status=='BLOCKED':
                with db.connect() as c:_guard(c)  # No continuation until passive general health clears a target hold.
    except Exception as error:reason=str(error);status='STOPPED'
    finally:
        with db.connect() as c:
            for row in c.execute('SELECT * FROM selective_items WHERE run_id=? AND after_json IS NULL',(ident,)).fetchall():
                saved=json.loads(row['steps_json'])
                if any(v.get('status')=='COLLECTED' for v in saved.values() if isinstance(v,dict)):
                    try:c.execute('UPDATE selective_items SET after_json=? WHERE run_id=? AND video_id=?',(encode(intelligence(c,row['video_id'],True)),ident,row['video_id']))
                    except Exception as error:
                        saved['recompute_error']=str(error);c.execute('UPDATE selective_items SET steps_json=? WHERE run_id=? AND video_id=?',(encode(saved),ident,row['video_id']))
            c.execute("UPDATE selective_items SET status='INTERRUPTED' WHERE run_id=? AND status='RUNNING'",(ident,))
            c.execute('UPDATE selective_runs SET status=?,finished_at=?,stop_reason=? WHERE id=?',(status,now(),reason,ident))
        worker_context.reset(legacy);CONTEXT.reset(token)
    return report(ident)


def report(ident):
    with db.connect() as c:
        run=dict(c.execute('SELECT * FROM selective_runs WHERE id=?',(ident,)).fetchone())
        items=[]
        for row in c.execute('SELECT * FROM selective_items WHERE run_id=? ORDER BY video_id',(ident,)):
            item=dict(row)
            for key in ('priority_json','before_json','after_json','steps_json'):
                value=item.pop(key);item[key[:-5]]=json.loads(value) if value else None
            detail=c.execute('SELECT * FROM video_detail_observations WHERE command_id=?',(item['steps'].get('detail',{}).get('command_id'),)).fetchone()
            if detail:
                fields=json.loads(detail['fields_json']);item['detail_summary']={'observed_at':detail['observed_at'],'observation_id':detail['id'],'fields':{k:fields.get(k) for k in ('likes','comments_count','shares','favorites','views','caption')},'hashtags':re.findall(r'#[\w]+',fields.get('caption') or ''),'hashtag_provenance':{'method':'derived_from_visible_caption','source_id':detail['id']},'field_evidence':json.loads(detail['field_evidence_json'])}
            items.append(item)
        bridge=safe.state(c,'tiktok_bridge')
        checkpoint=json.loads(run['checkpoint_json']);checkpoint['unselected_digest_after']=unselected_digest(c,[x['video_id'] for x in items]);checkpoint['unselected_unchanged']=checkpoint.get('unselected_digest_before')==checkpoint['unselected_digest_after'];run['checkpoint']=checkpoint
        counts={step:sum(x['steps'].get(step,{}).get('status')=='COLLECTED' for x in items) for step in TYPES}
        comments=c.execute('SELECT count(*) FROM comment_observations WHERE sample_id IN (SELECT id FROM comment_samples WHERE command_id IN (SELECT id FROM bridge_commands WHERE json_extract(options_json,\'$.selective_run_id\')=?))',(ident,)).fetchone()[0]
        return {'run':run,'items':items,'selected':len(items),'enriched':sum(x['status']=='ENRICHED' for x in items),'skipped':sum(x['status']=='SELECTED' for x in items),'blocked':sum(x['status']=='BLOCKED' for x in items),'blocked_targets':target_safety.rows(c),'details_collected':counts['detail'],'comment_samples_collected':counts['comments'],'comments_collected':comments,'creators_collected':counts['creator'],'final_page':bridge.get('current_page_status'),'session':bridge.get('tiktok_session_status'),'global_security':safe.state(c,'browser_security_stop'),'stop_reason':run['stop_reason']}


def recover(c):
    c.execute("UPDATE selective_runs SET status='INTERRUPTED',finished_at=?,stop_reason='BACKEND_RESTARTED_NO_RETRY' WHERE status='RUNNING'",(now(),))
