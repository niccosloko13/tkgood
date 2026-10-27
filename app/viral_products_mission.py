"""Temporary, explicit search-only contract for the Viral Products 72h mission."""
import json,secrets
from datetime import datetime,timezone
from fastapi import HTTPException
from . import safe_collection as safe
from .safety import SafetyGate

MISSION='viral-products-72h'
CONTRACT={'mission':MISSION,'max_queries':20,'max_results_per_query':10,'max_results_total':200,
          'max_unique_new_videos':100,'max_scrolls':0,'direct_video_enrichment':'PAUSED',
          'engagement':'FORBIDDEN','expires_after_completion':True}

def migrate(c):
    c.execute('''CREATE TABLE IF NOT EXISTS viral_products_72h_missions (
      id TEXT PRIMARY KEY,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
      extension_id TEXT NOT NULL,tab_id INTEGER NOT NULL,queries_json TEXT NOT NULL,query_index INTEGER NOT NULL DEFAULT 0,
      command_id INTEGER,results INTEGER NOT NULL DEFAULT 0,new_videos INTEGER NOT NULL DEFAULT 0,
      duplicates INTEGER NOT NULL DEFAULT 0,observations INTEGER NOT NULL DEFAULT 0,snapshots INTEGER NOT NULL DEFAULT 0,
      errors_json TEXT NOT NULL DEFAULT '[]',stop_reason TEXT,contract_json TEXT NOT NULL)''')

def _now(): return datetime.now(timezone.utc).isoformat()
def _state(c,key): return safe.state(c,key)

def start(c,queries):
    migrate(c); queries=[' '.join(q.split()) for q in queries if isinstance(q,str) and q.strip()]
    if not queries or len(queries)>CONTRACT['max_queries'] or len(set(queries))!=len(queries):raise HTTPException(422,'1-20 unique mission queries required')
    if c.execute("SELECT 1 FROM viral_products_72h_missions WHERE status IN ('RUNNING','PENDING')").fetchone():raise HTTPException(409,'Viral Products 72h mission already active')
    bridge=_state(c,'tiktok_bridge'); latch=_state(c,'browser_security_stop')
    if latch.get('reason'):raise HTTPException(409,'SECURITY_BLOCK: mission refused')
    if _state(c,'direct_video_enrichment').get('status')!='PAUSED':raise HTTPException(409,'DIRECT_VIDEO_ENRICHMENT must remain PAUSED')
    if not SafetyGate.assess(bridge,bridge.get('extension_id',''),bridge.get('build_id','')).may_continue:raise HTTPException(409,'Healthy confirmed TikTok tab required')
    if bridge.get('safe_collection_version')!='v1':raise HTTPException(409,'Bounded Companion required')
    ident=secrets.token_hex(16); stamp=_now()
    c.execute('INSERT INTO viral_products_72h_missions(id,status,created_at,updated_at,extension_id,tab_id,queries_json,contract_json) VALUES (?,\'RUNNING\',?,?,?,?,?,?)',
              (ident,stamp,stamp,bridge['extension_id'],bridge['tab_id'],json.dumps(queries,ensure_ascii=False),json.dumps(CONTRACT)))
    return advance(c,ident)

def command_allowed(c,row):
    try: ident=json.loads(row['options_json']).get('mission_contract_id')
    except (TypeError,ValueError): return False
    job=c.execute('SELECT * FROM viral_products_72h_missions WHERE id=?',(ident,)).fetchone()
    if not job or job['status']!='RUNNING' or job['command_id']!=row['id']:return False
    bridge=_state(c,'tiktok_bridge')
    return (not _state(c,'browser_security_stop').get('reason') and row['type']=='READ_SEARCH_RESULTS'
            and bridge.get('tab_id')==job['tab_id'] and bridge.get('extension_id')==job['extension_id']
            and SafetyGate.assess(bridge,job['extension_id'],bridge.get('build_id','')).may_continue)

def advance(c,ident):
    job=c.execute('SELECT * FROM viral_products_72h_missions WHERE id=?',(ident,)).fetchone()
    if not job or job['status']!='RUNNING':raise HTTPException(409,'Mission not running')
    if _state(c,'browser_security_stop').get('reason'):
        c.execute('UPDATE viral_products_72h_missions SET status=\'BLOCKED\',stop_reason=\'GLOBAL_SECURITY_EVENT\',updated_at=? WHERE id=?',(_now(),ident));raise HTTPException(409,'SECURITY_BLOCK')
    queries=json.loads(job['queries_json'])
    if job['query_index']>=len(queries) or job['results']>=CONTRACT['max_results_total'] or job['new_videos']>=CONTRACT['max_unique_new_videos']:
        c.execute('UPDATE viral_products_72h_missions SET status=\'SUCCEEDED\',stop_reason=?,updated_at=? WHERE id=?',('MISSION_LIMIT_REACHED',_now(),ident));return report(c,ident)
    bridge=_state(c,'tiktok_bridge')
    if not SafetyGate.assess(bridge,job['extension_id'],bridge.get('build_id','')).may_continue:raise HTTPException(409,'Healthy confirmed page required')
    query=queries[job['query_index']]
    options={'mission_contract_id':ident,'max_results':CONTRACT['max_results_per_query'],'max_scrolls':0,'max_runtime':60,
             'navigate_search':True,'expected_tab_id':job['tab_id'],'validated_url':bridge.get('current_url')}
    cur=c.execute("INSERT INTO bridge_commands(created_at,updated_at,type,query,status,extension_id,options_json) VALUES (?,?,'READ_SEARCH_RESULTS',?,'PENDING',?,?)",(_now(),_now(),query,job['extension_id'],json.dumps(options)))
    c.execute('UPDATE viral_products_72h_missions SET command_id=?,query_index=query_index+1,updated_at=? WHERE id=?',(cur.lastrowid,_now(),ident))
    return {'id':ident,'command_id':cur.lastrowid,'query':query,'status':'PENDING','contract':CONTRACT}

def finish(c,row,status,capture,inserted,updated):
    ident=json.loads(row['options_json']).get('mission_contract_id'); job=c.execute('SELECT * FROM viral_products_72h_missions WHERE id=?',(ident,)).fetchone()
    if not job:return
    errors=json.loads(job['errors_json']); seen=len(capture.get('results',[])) if capture else 0
    if status!='SUCCEEDED':errors.append({'query':row['query'],'command_id':row['id'],'reason':row['detail'][:500]})
    snaps=c.execute("SELECT count(*) FROM trend_snapshot_sources p JOIN search_observations o ON p.source_key='search_observations:'||o.id WHERE o.capture_id=?",(f'command:{row["id"]}',)).fetchone()[0]
    if _state(c,'browser_security_stop').get('reason'):
        c.execute("UPDATE viral_products_72h_missions SET status='BLOCKED',stop_reason='GLOBAL_SECURITY_EVENT',errors_json=?,updated_at=? WHERE id=?",(json.dumps(errors),_now(),ident));return
    c.execute('UPDATE viral_products_72h_missions SET results=results+?,new_videos=new_videos+?,duplicates=duplicates+?,observations=observations+?,snapshots=snapshots+?,errors_json=?,updated_at=? WHERE id=?',
              (seen,inserted,updated,seen,snaps,json.dumps(errors),_now(),ident))
    advance(c,ident)

def post_capture(c,command_id):
    from .trend_engine_v2 import recompute
    from .search_intelligence import rebuild
    recompute(c); rebuild(c)

def report(c,ident):
    row=c.execute('SELECT * FROM viral_products_72h_missions WHERE id=?',(ident,)).fetchone()
    if not row:return None
    d=dict(row);d['queries']=json.loads(d.pop('queries_json'));d['errors']=json.loads(d.pop('errors_json'));d['contract']=json.loads(d.pop('contract_json'));return d
