"""Canonical durable search-only discovery lifecycle and bounded runner."""
import json,re,secrets
from datetime import datetime,timezone,timedelta
from fastapi import HTTPException
from . import safe_collection as safe
from .safety import SafetyGate
migrate=safe.migrate
state=safe.state
now=safe.now
encoded=safe.encoded
put=safe.put
authorize_healthy_stage1=safe.authorize_healthy_stage1
MAX_STAGE2_QUERIES=safe.MAX_STAGE2_QUERIES
MAX_STAGE2_NEW=safe.MAX_STAGE2_NEW
MAX_RUNTIME_SECONDS=safe.MAX_RUNTIME_SECONDS
from pathlib import Path
PLAN=json.loads((Path(__file__).resolve().parents[1]/'config/discovery_contract.json').read_text())

class DiscoveryPlan:
    """Shared bounded Stage 1/2 configuration; both stages remain search-only."""
    @staticmethod
    def build(stage,queries):
        if stage not in (1,2):raise HTTPException(422,'Unsupported discovery stage')
        policy=PLAN['stages'][str(stage)]
        if not isinstance(queries,list) or not queries or len(queries)>policy['max_queries']:raise HTTPException(422,'Bounded unique query list required')
        if any(not isinstance(q,str) or not q.strip() or len(q)>200 for q in queries):raise HTTPException(422,'Invalid search query')
        if len(set(queries))!=len(queries):raise HTTPException(422,'Duplicate search query')
        if policy['search_only'] is not True or policy['max_scrolls']!=0:raise RuntimeError('Unsafe discovery plan configuration')
        return {**policy,'stage':stage,'queries':list(queries)}

class DiscoveryRunner:
    """One persisted lifecycle for both stages; stage only sets the fixed budget."""
    @classmethod
    def start(cls,con,ident,queries,stage=1,allow_explicit_unobserved=False):
        plan=DiscoveryPlan.build(stage,queries)
        migrate(con)
        if stage not in (1,2) or not queries or len(queries)>(1 if stage==1 else MAX_STAGE2_QUERIES) or len(set(queries))!=len(queries):raise HTTPException(422,'Bounded unique query list required')
        if stage==2 and not con.execute("SELECT 1 FROM safe_collection_batches WHERE stage=1 AND status='SUCCEEDED' AND validation_id=?",(ident,)).fetchone():raise HTTPException(409,'Stage 1 must pass for this validation first')
        if stage==2 and con.execute('SELECT 1 FROM safe_collection_batches WHERE stage=2 AND validation_id=?',(ident,)).fetchone():raise HTTPException(409,'Stage 2 already attempted for this validation; no retry')
        if stage==1 and con.execute('SELECT 1 FROM safe_collection_batches WHERE stage=1 AND validation_id=?',(ident,)).fetchone():raise HTTPException(409,'Stage 1 already attempted for this validation; no retry')
        check=con.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(ident,)).fetchone()
        if not check or not check['release_json']:raise HTTPException(409,'Explicit release required')
        stage2auth=con.execute('SELECT * FROM safe_stage2_authorizations WHERE validation_id=?',(ident,)).fetchone() if stage==2 else None
        if json.loads(check['release_json']).get('authorization_type')=='SEARCH_ONLY_STAGE1' and stage!=1 and not stage2auth:raise HTTPException(409,'This authorization is Stage 1 search-only')
        if stage2auth and queries!=json.loads(stage2auth['queries_json']):raise HTTPException(409,'Queries differ from explicit Stage 2 pack authorization')
        guard=state(con,'safe_collection_guard')
        if not guard.get('enabled') or guard.get('validation_id')!=ident:raise HTTPException(409,'Matching safe collection guard required')
        for query in queries:
            if not isinstance(query,str) or not query.strip() or len(query)>200:raise HTTPException(422,'Invalid query')
            if (not stage2auth and not con.execute('SELECT 1 FROM search_observations WHERE search_query=?',(query,)).fetchone()
                    and not (stage==1 and allow_explicit_unobserved)):
                raise HTTPException(409,'Only previously observed queries are allowed')
        batch=secrets.token_hex(16)
        con.execute("INSERT INTO safe_collection_batches(id,stage,status,created_at,validation_id,queries_json) VALUES (?,?,'READY',?,?,?)",(batch,stage,now(),ident,encoded(queries)))
        return cls.advance(con,batch)
    @classmethod
    def advance(cls,con,batch):
        row=con.execute('SELECT * FROM safe_collection_batches WHERE id=?',(batch,)).fetchone()
        if not row or row['status'] not in ('READY','PAUSED'):raise HTTPException(409,'Batch stopped; no automatic continuation')
        bridge=state(con,'tiktok_bridge');check=cls.collection_check(con,row)
        if state(con,'browser_security_stop').get('reason'):raise HTTPException(409,'SECURITY_BLOCK: zero retries')
        if state(con,'target_security_pending').get('items'):raise HTTPException(409,'Target HTTP 403: passive healthy home/search required')
        if not SafetyGate.assess(bridge,check['extension_id'],check['build_id']).may_continue:raise HTTPException(409,'HEALTHY current page required')
        if bridge.get('safe_collection_version')!='v1':raise HTTPException(409,'Bounded capture Companion build required')
        budget=PLAN['stages'][str(row['stage'])]
        remaining=budget['max_runtime_seconds']-cls.runtime_used(con,row)
        if remaining<=0:raise HTTPException(409,'Bounded runtime reached')
        if row['stage']==2 and remaining<35:raise HTTPException(409,'Insufficient runtime for another bounded viewport')
        queries=json.loads(row['queries_json'])
        if row['query_index']>=len(queries) or row['new_videos']>=budget['max_new_videos']:raise HTTPException(409,'Hard limit reached')
        from .dev_control import active_operations
        if any(active_operations(con).values()):raise HTTPException(409,'Another operation owns the tab')
        cap=min(budget['max_results_per_query'],budget['max_new_videos']-row['new_videos'])
        options={'safe_collection_id':batch,'max_results':cap,'navigate_search':True,'max_scrolls':0,'max_runtime':60,'expected_tab_id':bridge['tab_id'],'validated_url':bridge['current_url']}
        if row['stage']==2:
            options['deadline_at']=(datetime.now(timezone.utc)+timedelta(seconds=remaining)).isoformat()
            options['strict_health']=True
        cur=con.execute("INSERT INTO bridge_commands(created_at,updated_at,type,query,status,extension_id,options_json) VALUES (?,?,'READ_SEARCH_RESULTS',?,'PENDING',?,?)",(now(),now(),queries[row['query_index']],check['extension_id'],encoded(options)))
        con.execute("UPDATE safe_collection_batches SET status='PENDING',command_id=?,query_index=query_index+1 WHERE id=?",(cur.lastrowid,batch))
        return {'id':batch,'command_id':cur.lastrowid,'stage':row['stage'],'max_results':cap,'status':'PENDING'}
    @classmethod
    def command_allowed(cls,con,row):
        if state(con,'target_security_pending').get('items'):return False
        try:
            mission_id=json.loads(row['options_json']).get('mission_contract_id')
        except (TypeError,ValueError):mission_id=None
        if mission_id:
            from .viral_products_mission import command_allowed
            return command_allowed(con,row)
        if json.loads(row['options_json']).get('selective_run_id'):
            from .selective_enrichment import command_allowed as selective_allowed
            return selective_allowed(con,row)
        guard=state(con,'safe_collection_guard')
        if not guard.get('enabled'):return True
        if row['type']!='READ_SEARCH_RESULTS':return False
        batch=con.execute("SELECT * FROM safe_collection_batches WHERE command_id=? AND status='PENDING'",(row['id'],)).fetchone()
        if not batch or guard.get('validation_id')!=batch['validation_id']:return False
        check=cls.collection_check(con,batch)
        bridge=state(con,'tiktok_bridge')
        return bool(check and bridge.get('safe_collection_version')=='v1' and
            SafetyGate.assess(bridge,check['extension_id'],check['build_id']).may_continue and
            cls.runtime_used(con,batch)<PLAN['stages'][str(batch['stage'])]['max_runtime_seconds'])
    @classmethod
    def runtime_used(cls,con,batch):
        clock=datetime.fromisoformat(batch['completed_at']) if batch['status'] in ('SUCCEEDED','FAILED') and batch['completed_at'] else datetime.now(timezone.utc)
        resume=con.execute('SELECT * FROM safe_stage2_resumptions WHERE batch_id=?',(batch['id'],)).fetchone()
        if resume:return resume['prior_elapsed_seconds']+(clock-datetime.fromisoformat(resume['resumed_at'])).total_seconds()
        return (clock-datetime.fromisoformat(batch['created_at'])).total_seconds()
    @classmethod
    def collection_check(cls,con,batch):
        resume=con.execute('SELECT fresh_check_id FROM safe_stage2_resumptions WHERE batch_id=?',(batch['id'],)).fetchone()
        if resume:return con.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(resume['fresh_check_id'],)).fetchone()
        auth=con.execute('SELECT fresh_check_id FROM safe_stage2_authorizations WHERE validation_id=?',(batch['validation_id'],)).fetchone() if batch['stage']==2 else None
        return con.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(auth['fresh_check_id'] if auth else batch['validation_id'],)).fetchone()
    @classmethod
    def finish(cls,con,row,status,capture,inserted=0,updated=0):
        options=json.loads(row['options_json']);batch=options.get('safe_collection_id')
        if not batch:return
        job=con.execute('SELECT * FROM safe_collection_batches WHERE id=? AND command_id=?',(batch,row['id'])).fetchone()
        if not job:raise ValueError('Safe collection ownership mismatch')
        seen=len(capture['results']) if capture else 0
        snaps=con.execute("SELECT count(*) FROM trend_snapshot_sources p JOIN search_observations o ON p.source_key='search_observations:'||o.id WHERE o.capture_id=?",(f"command:{row['id']}",)).fetchone()[0]
        budget=PLAN['stages'][str(job['stage'])]
        final='FAILED' if status!='SUCCEEDED' else 'SUCCEEDED' if job['stage']==1 or job['query_index']>=len(json.loads(job['queries_json'])) or job['new_videos']+inserted>=budget['max_new_videos'] else 'PAUSED'
        reason='COMMAND_FAILED_NO_RETRY' if status!='SUCCEEDED' else 'CAPTURE_COMPLETED_STOP' if job['stage']==1 else 'MAX_NEW_VIDEOS' if job['new_videos']+inserted>=budget['max_new_videos'] else 'MAX_QUERIES' if final=='SUCCEEDED' else 'OPERATOR_ADVANCE_REQUIRED'
        con.execute('UPDATE safe_collection_batches SET status=?,new_videos=new_videos+?,seen=seen+?,duplicates=duplicates+?,snapshots=?,stop_reason=?,completed_at=? WHERE id=?',
            (final,inserted,seen,updated,job['snapshots']+snaps,reason,now(),batch))
        if job['stage']==2:
            from .target_safety import blocked
            observations=[dict(r) for r in con.execute('SELECT * FROM search_observations WHERE capture_id=?',(f"command:{row['id']}",))]
            fields=[json.loads(r['fields_json']) for r in observations]
            creators={v['creator_username'] for v in fields if v.get('creator_username')}
            blocked_count=sum(blocked(con,v.get('video_url','')) for v in fields)
            matches=sum(bool(con.execute("SELECT 1 FROM video_category_classifications WHERE id=(SELECT max(id) FROM video_category_classifications WHERE video_id=?) AND primary_category='home'",(r['video_id'],)).fetchone()) for r in observations)
            observed=max((r['observed_at'] for r in observations),default=now())
            con.execute('INSERT INTO safe_query_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(row['id'],batch,row['query'],status,seen,inserted,updated,blocked_count,(capture or {}).get('invalid_results',0),len(creators),matches,observed,snaps))
    @classmethod
    def post_capture(cls,con,command_id):
        from .category_intelligence import classify_library
        from .intelligence_core import observation,work_payload
        from .intelligence_jobs import enqueue
        ids=[r[0] for r in con.execute('SELECT video_id FROM search_observations WHERE capture_id=?',(f'command:{command_id}',))]
        if ids:classify_library(con,ids)
        # Offline deterministic projection over the observations just persisted.
        # It never schedules browser work or alters the Safety latch.
        from .trend_engine_v2 import recompute as recompute_opportunities
        recompute_opportunities(con)
        batch=con.execute('SELECT stage FROM safe_collection_batches WHERE command_id=?',(command_id,)).fetchone()
        if batch and batch['stage']==2:return  # Search-only Stage 2 never schedules resolver/enrichment work.
        for vid in ids:enqueue(con,'identity',vid,work_payload(con,observation(con,vid)))

    @classmethod
    def report(cls,con,batch_id):
        row=con.execute('SELECT * FROM safe_collection_batches WHERE id=?',(batch_id,)).fetchone()
        if not row:return None
        queries=json.loads(row['queries_json']);command_ids=[r[0] for r in con.execute('SELECT id FROM bridge_commands WHERE json_extract(options_json,\'$.safe_collection_id\')=? ORDER BY id',(batch_id,))]
        observations=0;snapshots=0;metrics=[]
        if command_ids:
            captures=[f'command:{ident}' for ident in command_ids];slots=','.join('?' for _ in captures)
            observations=con.execute(f'SELECT count(*) FROM search_observations WHERE capture_id IN ({slots})',captures).fetchone()[0]
            snapshots=con.execute(f"SELECT count(*) FROM trend_snapshot_sources WHERE source_key LIKE 'search_observations:%' AND source_key IN (SELECT 'search_observations:'||id FROM search_observations WHERE capture_id IN ({slots}))",captures).fetchone()[0]
            metrics=[dict(r) for r in con.execute(f'SELECT * FROM safe_query_metrics WHERE batch_id=? ORDER BY command_id',(batch_id,))]
        return {'stage':row['stage'],'queries':queries,'status':row['status'],'query_index':row['query_index'],'results':row['seen'],'new_videos':row['new_videos'],'duplicates':row['duplicates'],'observations':observations,'trend_snapshots':snapshots,'stop_reason':row['stop_reason'],'checkpoint':{'batch_id':batch_id,'command_ids':command_ids,'created_at':row['created_at'],'completed_at':row['completed_at'],'metrics':metrics}}
    @classmethod
    def authorize_stage2(cls,con,ident,fresh,queries,extension_id):
        migrate(con)
        passed=con.execute("SELECT 1 FROM safe_collection_batches WHERE stage=1 AND status='SUCCEEDED' AND validation_id=?",(ident,)).fetchone()
        if not passed:raise HTTPException(409,'Stage 1 success required')
        if con.execute('SELECT 1 FROM safe_collection_batches WHERE stage=2 AND validation_id=?',(ident,)).fetchone():raise HTTPException(409,'Stage 2 already attempted; no retry')
        if con.execute('SELECT 1 FROM safe_stage2_authorizations WHERE validation_id=?',(ident,)).fetchone():raise HTTPException(409,'Stage 2 authorization already exists')
        from .category_intelligence import config
        pack={q[0] for q in config('discovery_intelligence')['queries'] if q[1]=='home'}
        if not queries or len(queries)>MAX_STAGE2_QUERIES or len(set(queries))!=len(queries) or not set(queries)<=pack:raise HTTPException(422,'At most five unique queries from current Casa pack required')
        # Reuse the existing two-sample, no-latch, no-active-command authorization gate.
        authorize_healthy_stage1(con,fresh,extension_id)
        old=con.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(ident,)).fetchone()
        check=con.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(fresh,)).fetchone()
        if old['extension_id']!=extension_id:raise HTTPException(409,'Passed Stage 1 Companion identity changed')
        con.execute('INSERT INTO safe_stage2_authorizations VALUES (?,?,?,?)',(ident,fresh,encoded(queries),now()))
        put(con,'safe_collection_guard',{'enabled':True,'validation_id':ident})
        return {'validation_id':ident,'queries':queries,'max_queries':MAX_STAGE2_QUERIES,'max_new_videos':MAX_STAGE2_NEW,'max_runtime_seconds':MAX_RUNTIME_SECONDS}
    @classmethod
    def resume_stage2(cls,con,batch_id,fresh,extension_id):
        """One explicit resume of a zero-observation transient failure; same batch."""
        migrate(con)
        existing=con.execute('SELECT * FROM safe_stage2_resumptions WHERE batch_id=?',(batch_id,)).fetchone()
        if existing:
            return {'id':batch_id,'command_id':existing['command_id'],'stage':2,'reused':True}
        job=con.execute('SELECT * FROM safe_collection_batches WHERE id=?',(batch_id,)).fetchone()
        if not job or job['stage']!=2 or job['status']!='FAILED':raise HTTPException(409,'Interrupted Stage 2 batch required')
        command=con.execute('SELECT * FROM bridge_commands WHERE id=?',(job['command_id'],)).fetchone()
        if not command or command['status']!='FAILED' or command['extension_id']!=extension_id:raise HTTPException(409,'Matching failed command required')
        if re.search(r'403|access.denied|challenge|captcha|verify.*human|LOGGED_OUT|UNEXPECTED_HOST|SEARCH_ROUTE_INVALID',command['detail'],re.I):raise HTTPException(409,'Hard-stop commands cannot resume')
        if not ('Stage 2 session/page not healthy' in command['detail'] or 'SESSION_NOT_STABLE' in command['detail']):raise HTTPException(409,'Only transient stability failure may resume; no hard-stop retry')
        if con.execute('SELECT 1 FROM search_observations WHERE capture_id=?',(f"command:{command['id']}",)).fetchone():raise HTTPException(409,'Interrupted query already persisted; resume refused')
        queries=json.loads(job['queries_json']);index=job['query_index']-1
        if index<0 or queries[index]!=command['query']:raise HTTPException(409,'Checkpoint query mismatch')
        if con.execute("SELECT 1 FROM safe_query_metrics WHERE batch_id=? AND query=? AND status='SUCCEEDED'",(batch_id,command['query'])).fetchone():raise HTTPException(409,'Query already completed')
        prior_elapsed=max(0,(datetime.fromisoformat(job['completed_at'])-datetime.fromisoformat(job['created_at'])).total_seconds())
        budget=PLAN['stages']['2']
        if prior_elapsed>=budget['max_runtime_seconds']-35 or job['new_videos']>=budget['max_new_videos']:raise HTTPException(409,'Original budget exhausted')
        # Fresh two-sample evidence; this does not clear security or replace Stage 1.
        authorize_healthy_stage1(con,fresh,extension_id)
        con.execute('INSERT INTO safe_stage2_resumptions VALUES (?,?,?,?,?,NULL)',(batch_id,fresh,now(),prior_elapsed,encoded(dict(job))))
        put(con,'safe_collection_guard',{'enabled':True,'validation_id':job['validation_id']})
        con.execute("UPDATE safe_collection_batches SET status='PAUSED',query_index=?,stop_reason='EXPLICIT_TRANSIENT_RESUME',completed_at=NULL WHERE id=?",(index,batch_id))
        result=cls.advance(con,batch_id)
        con.execute('UPDATE safe_stage2_resumptions SET command_id=? WHERE batch_id=?',(result['command_id'],batch_id))
        return {**result,'reused':False,'prior_elapsed_seconds':prior_elapsed}
