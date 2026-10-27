"""Bounded resumable coordinator for existing commands. Never clears a security latch."""
import contextvars
from datetime import datetime,timezone
import json
import threading
import time
from . import db,category_intelligence as ci

worker_context=contextvars.ContextVar('night_discovery_worker',default=False)
LOCK=threading.Lock()

def checkpoint(con,run_id,query,stage,data,session_id=None):
    con.execute('INSERT INTO night_discovery_checkpoints(run_id,session_id,query,stage,data_json,created_at) VALUES (?,?,?,?,?,?)',
        (run_id,session_id,query,stage,ci.encoded(data),ci.now()))
    con.execute('UPDATE night_discovery_runs SET checkpoint_json=?,updated_at=? WHERE id=?',(ci.encoded(data),ci.now(),run_id))

def stop_reason(settings,progress,elapsed):
    if elapsed>=settings['max_runtime_seconds']:return 'max_runtime'
    if progress.get('sessions',0)>=settings['max_sessions']:return 'max_sessions'
    if progress.get('new_videos',0)>=settings['max_total_new_videos']:return 'max_total_new_videos'
    return None

class Adapter:
    def security(self):
        latch=db.get_state('browser_security_stop',{})
        if latch.get('reason'):return latch['reason']
        from .main import live_bridge
        bridge=live_bridge()
        if not bridge.get('connected'):return 'Companion/session not ready'
        if bridge.get('tiktok_session_status')!='confirmed':return 'session_unconfirmed'
        if bridge.get('current_page_status')!='healthy':return 'current_page_not_healthy'
        return None
    def submit(self,kind,query,limit):
        from .main import create_command
        from .schemas import SearchCommand,DiscoveryCommand
        body=SearchCommand(type='SEARCH',query=query) if kind=='SEARCH' else DiscoveryCommand(type='DISCOVER_MORE_RESULTS',query=query,max_new_videos=limit)
        return create_command(body)['id']
    def state(self,command_id):
        with db.connect() as con:
            row=con.execute('SELECT * FROM bridge_commands WHERE id=?',(command_id,)).fetchone()
            return dict(row) if row else None
    def session(self,command_id):
        with db.connect() as con:
            row=con.execute('SELECT * FROM discovery_sessions WHERE command_id=?',(command_id,)).fetchone()
            return dict(row) if row else None
    def ready(self,query):
        from .main import live_bridge
        from urllib.parse import urlsplit,parse_qs
        bridge=live_bridge();url=urlsplit(bridge.get('url',''));signals=bridge.get('page_signals',{})
        return (bridge.get('tiktok_session_status')=='confirmed' and bridge.get('current_page_status')=='healthy' and
            url.path.rstrip('/')=='/search' and parse_qs(url.query).get('q',[''])[0]==query
            and bool(signals.get('content_script_connected')) and signals.get('ready_state')=='complete')

def start(resume_id=None):
    if not LOCK.acquire(False):raise ValueError('A night runner is already active')
    try:
        with db.connect() as con:
            con.execute("UPDATE night_discovery_runs SET status='interrupted',stop_reason='worker_missing' WHERE status='running'")
            if con.execute("SELECT 1 FROM enrichment_batches WHERE status='running'").fetchone():raise ValueError('Enrichment owns the tab')
            active_commands={r[0] for r in con.execute("SELECT id FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED')")}
            if active_commands:
                resumed=con.execute('SELECT checkpoint_json FROM night_discovery_runs WHERE id=?',(resume_id,)).fetchone() if resume_id else None
                expected=json.loads(resumed[0]).get('command_id') if resumed else None
                if active_commands!={expected}:raise ValueError('An existing command owns the tab; no interruption attempted')
            if resume_id:
                row=con.execute('SELECT * FROM night_discovery_runs WHERE id=?',(resume_id,)).fetchone()
                if not row or row['status'] not in ('waiting','interrupted','stopped'):raise ValueError('Run cannot be resumed')
                con.execute("UPDATE night_discovery_runs SET status='running',stop_requested=0,stop_reason=NULL WHERE id=?",(resume_id,));rid=resume_id
            else:
                settings=ci.config('discovery_intelligence')['runner']
                rid=con.execute("INSERT INTO night_discovery_runs(created_at,updated_at,status,settings_json) VALUES (?,?,'running',?)",
                    (ci.now(),ci.now(),ci.encoded(settings))).lastrowid
        threading.Thread(target=run,args=(rid,),daemon=True,name='bounded-night-discovery').start()
        return rid
    except Exception:
        LOCK.release();raise

def run(run_id,adapter=None,clock=time.monotonic,sleep=time.sleep):
    adapter=adapter or Adapter();token=worker_context.set(True);began=clock()
    try:
        with db.connect() as con:
            row=con.execute('SELECT * FROM night_discovery_runs WHERE id=?',(run_id,)).fetchone()
            settings=json.loads(row['settings_json']);progress=json.loads(row['checkpoint_json'])
            elapsed_before=max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(row['created_at'])).total_seconds())
        progress.setdefault('sessions',0);progress.setdefault('new_videos',0);progress.setdefault('queries',[])
        while True:
            security=adapter.security()
            if security:return finish(run_id,'security_stop',security)
            with db.connect() as con:
                row=con.execute('SELECT stop_requested FROM night_discovery_runs WHERE id=?',(run_id,)).fetchone()
                if row['stop_requested']:return finish(run_id,'manual_stop')
            reason=stop_reason(settings,progress,clock()-began+elapsed_before)
            if reason:return finish(run_id,reason)
            query=progress.get('active_query')
            if not query:
                with db.connect() as con:plan=ci.plan(con,excluded=progress['queries'])
                query=plan['selected_query']
                if not query:return finish(run_id,'queries_exhausted')
                progress.update(active_query=query,stage='SEARCH',command_id=None)
                with db.connect() as con:checkpoint(con,run_id,query,'selected',progress)
            stage=progress['stage']
            if stage in ('SEARCH','DISCOVER_MORE_RESULTS'):
                if stage=='DISCOVER_MORE_RESULTS' and not adapter.ready(query):
                    deadline=clock()+settings['command_timeout_seconds']
                    while not adapter.ready(query):
                        if adapter.security():return finish(run_id,'security_stop',adapter.security())
                        if clock()>=deadline:return finish(run_id,'readiness_timeout')
                        if stop_reason(settings,progress,clock()-began+elapsed_before):return finish(run_id,'max_runtime')
                        sleep(settings['poll_seconds'])
                if not progress.get('command_id'):
                    if adapter.security():return finish(run_id,'security_stop',adapter.security())
                    limit=min(settings['max_new_videos_per_session'],settings['max_total_new_videos']-progress['new_videos'])
                    progress['command_id']=adapter.submit(stage,query,limit)
                    with db.connect() as con:checkpoint(con,run_id,query,stage,progress)
                deadline=clock()+settings['command_timeout_seconds']
                while True:
                    if adapter.security():return finish(run_id,'security_stop',adapter.security())
                    command=adapter.state(progress['command_id'])
                    if not command:return finish(run_id,'command_missing')
                    if command['status'] in ('SUCCEEDED','FAILED','EXPIRED'):break
                    if stop_reason(settings,progress,clock()-began+elapsed_before):return finish(run_id,'max_runtime_command_active',status='waiting')
                    if clock()>=deadline:return finish(run_id,'command_still_active',status='waiting')
                    sleep(settings['poll_seconds'])
                if command['status']!='SUCCEEDED':return finish(run_id,'command_failed',command.get('detail'))
                if stage=='SEARCH':
                    progress.update(stage='DISCOVER_MORE_RESULTS',command_id=None)
                    with db.connect() as con:checkpoint(con,run_id,query,'search_complete',progress)
                    continue
                session=adapter.session(progress['command_id'])
                if not session:return finish(run_id,'session_missing')
                if session['stop_reason'] in ('security_challenge','error'):return finish(run_id,session['stop_reason'])
                progress.update(stage='PROCESS',session_id=session['id'])
                with db.connect() as con:checkpoint(con,run_id,query,'captured',progress,session['id'])
            if progress['stage']=='PROCESS':
                with db.connect() as con:
                    session=con.execute('SELECT * FROM discovery_sessions WHERE id=?',(progress['session_id'],)).fetchone()
                    vids=[r[0] for r in con.execute('SELECT video_id FROM discovery_session_videos WHERE session_id=?',(session['id'],))]
                    ci.classify_library(con,vids)
                from .product_detection import detect
                # Detector owns BEGIN IMMEDIATE: use its existing transaction boundary.
                for vid in vids:
                    with db.connect() as con:
                        detect(con,video_id=vid)
                        ci.classify_library(con,[vid])
                with db.connect() as con:
                    progress['sessions']+=1;progress['new_videos']+=session['new_videos'];progress['queries'].append(query)
                    progress['last_query_metrics']=next((q for q in ci.query_metrics(con) if q['query']==query),None)
                    progress.update(active_query=None,command_id=None,stage='SELECT')
                    checkpoint(con,run_id,query,'complete',progress,session['id'])
                sleep(settings['cooldown_seconds'])
    except Exception as exc:finish(run_id,'error',str(exc))
    finally:
        worker_context.reset(token)
        if LOCK.locked():LOCK.release()

def finish(run_id,reason,detail=None,status='stopped'):
    with db.connect() as con:
        con.execute('UPDATE night_discovery_runs SET status=?,stop_reason=?,updated_at=? WHERE id=?',(status,reason,ci.now(),run_id))
        row=con.execute('SELECT checkpoint_json FROM night_discovery_runs WHERE id=?',(run_id,)).fetchone()
        checkpoint(con,run_id,'','stop', {**json.loads(row[0]),'stop_detail':detail})

def recover():
    """A backend restart leaves durable progress available for explicit resume."""
    with db.connect() as con:
        con.execute("UPDATE night_discovery_runs SET status='interrupted',stop_reason='backend_restarted' WHERE status='running'")
