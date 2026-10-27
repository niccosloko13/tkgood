"""Explicit, non-navigating recovery checks and bounded search-only capture.

Heartbeat/check never clear a latch. Release is a separate authenticated operator
action. Stage 2 never starts or advances automatically.
"""
import json
import re
import secrets
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit,parse_qs
from fastapi import HTTPException

FRESH_SECONDS=15
CHECK_SAMPLES=2
_DISCOVERY_PLAN=json.loads((__import__('pathlib').Path(__file__).resolve().parents[1]/'config/discovery_contract.json').read_text())['stages']
MAX_STAGE1_RESULTS=_DISCOVERY_PLAN['1']['max_results_per_query']
MAX_STAGE2_QUERIES=_DISCOVERY_PLAN['2']['max_queries']
MAX_STAGE2_NEW=_DISCOVERY_PLAN['2']['max_new_videos']
MAX_RUNTIME_SECONDS=_DISCOVERY_PLAN['2']['max_runtime_seconds']


def now():return datetime.now(timezone.utc).isoformat()
def encoded(value):return json.dumps(value,sort_keys=True,ensure_ascii=False)
def state(con,key):
    row=con.execute('SELECT value_json FROM system_state WHERE key=?',(key,)).fetchone()
    return json.loads(row[0]) if row else {}
def put(con,key,value):
    con.execute('INSERT INTO system_state(key,value_json,updated_at) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at',(key,encoded(value),now()))


def migrate(con):
    con.execute('''CREATE TABLE IF NOT EXISTS safe_recovery_checks (
      id TEXT PRIMARY KEY,status TEXT NOT NULL,created_at TEXT NOT NULL,validated_at TEXT,
      extension_id TEXT NOT NULL,build_id TEXT NOT NULL,incident_json TEXT NOT NULL,
      samples_json TEXT NOT NULL DEFAULT '[]',evidence_json TEXT NOT NULL,release_json TEXT)''')
    con.execute('''CREATE TABLE IF NOT EXISTS safe_collection_batches (
      id TEXT PRIMARY KEY,stage INTEGER NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,
      validation_id TEXT NOT NULL REFERENCES safe_recovery_checks(id),queries_json TEXT NOT NULL,
      query_index INTEGER NOT NULL DEFAULT 0,command_id INTEGER,new_videos INTEGER NOT NULL DEFAULT 0,
      seen INTEGER NOT NULL DEFAULT 0,duplicates INTEGER NOT NULL DEFAULT 0,snapshots INTEGER NOT NULL DEFAULT 0,
      stop_reason TEXT,completed_at TEXT)''')
    con.execute('''CREATE TABLE IF NOT EXISTS safe_stage2_authorizations (
      validation_id TEXT PRIMARY KEY,fresh_check_id TEXT NOT NULL,queries_json TEXT NOT NULL,authorized_at TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS safe_query_metrics (
      command_id INTEGER PRIMARY KEY,batch_id TEXT NOT NULL,query TEXT NOT NULL,status TEXT NOT NULL,
      results INTEGER NOT NULL,new_videos INTEGER NOT NULL,duplicates INTEGER NOT NULL,blocked INTEGER NOT NULL,
      invalid INTEGER NOT NULL,unique_creators INTEGER NOT NULL,category_matches INTEGER NOT NULL,
      observed_at TEXT NOT NULL,snapshots INTEGER NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS safe_stage2_resumptions (
      batch_id TEXT PRIMARY KEY,fresh_check_id TEXT NOT NULL,resumed_at TEXT NOT NULL,
      prior_elapsed_seconds REAL NOT NULL,original_json TEXT NOT NULL,command_id INTEGER)''')
    con.execute('''CREATE TABLE IF NOT EXISTS safe_search_diagnostics (
      command_id INTEGER PRIMARY KEY,diagnostics_json TEXT NOT NULL,recorded_at TEXT NOT NULL)''')


def healthy_route(url):
    from .safety import SafetyGate
    return SafetyGate.healthy_route(url)



def health(bridge,extension_id,build_id):
    from .safety import SafetyGate
    return SafetyGate.health(bridge,extension_id,build_id)



def request_check(con,extension_id):
    migrate(con)
    if con.execute("SELECT 1 FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED')").fetchone():raise HTTPException(409,'Active content command; check refused')
    bridge=state(con,'tiktok_bridge');ident=secrets.token_hex(16);build=bridge.get('build_id','')
    evidence=health(bridge,extension_id,build);status='PENDING' if evidence['status']=='HEALTHY' else evidence['status']
    con.execute('INSERT INTO safe_recovery_checks(id,status,created_at,extension_id,build_id,incident_json,evidence_json) VALUES (?,?,?,?,?,?,?)',
        (ident,status,now(),extension_id,build,encoded(state(con,'browser_security_stop')),encoded(evidence)))
    return {'id':ident,'status':status,'evidence':evidence,'security_stop_released':False}


def observe_heartbeat(con,bridge):
    """Consume two fresh real heartbeat samples; no navigation or release side effect."""
    migrate(con)
    block=None
    for row in con.execute("SELECT * FROM safe_recovery_checks WHERE status='PENDING'").fetchall():
        evidence=health(bridge,row['extension_id'],row['build_id']);samples=json.loads(row['samples_json'])
        status=evidence['status']
        if state(con,'browser_security_stop')!=json.loads(row['incident_json']):status='UNKNOWN';evidence['reason']='INCIDENT_CHANGED'
        if not bridge.get('last_seen') or bridge['last_seen']<=row['created_at']:continue
        if (datetime.now(timezone.utc)-datetime.fromisoformat(row['created_at'])).total_seconds()>30:status='UNKNOWN';evidence['reason']='CHECK_EXPIRED'
        if status=='HEALTHY':
            if samples and any(samples[-1].get(k)!=evidence.get(k) for k in ('current_url','tab_id')):status='UNKNOWN';evidence['reason']='TAB_CHANGED'
            else:
                if not samples or samples[-1]['heartbeat_at']!=evidence['heartbeat_at']:samples.append(evidence)
                status='HEALTHY' if len(samples)>=CHECK_SAMPLES else 'PENDING'
        if status in ('BLOCKED','CHALLENGE'):block='SAFE_RECOVERY_CHECK '+status+': '+evidence['current_url']
        con.execute('UPDATE safe_recovery_checks SET status=?,validated_at=?,samples_json=?,evidence_json=? WHERE id=?',
            (status,now() if status=='HEALTHY' else None,encoded(samples),encoded(evidence),row['id']))
    return block


def release(con,ident,extension_id):
    row=con.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(ident,)).fetchone()
    if not row or row['status']!='HEALTHY' or row['release_json']:raise HTTPException(409,'Fresh HEALTHY manual check required; release is not automatic')
    incident=state(con,'browser_security_stop');bridge=state(con,'tiktok_bridge')
    if incident!=json.loads(row['incident_json']) or not re.search(r'403|access.denied',incident.get('reason',''),re.I):raise HTTPException(409,'Incident changed or is not a reviewed historical access block')
    current=health(bridge,extension_id,row['build_id']);previous=json.loads(row['evidence_json'])
    if (current['status']!='HEALTHY' or len(json.loads(row['samples_json']))<CHECK_SAMPLES or
        any(current.get(k)!=previous.get(k) for k in ('current_url','tab_id')) or
        (datetime.now(timezone.utc)-datetime.fromisoformat(row['validated_at'])).total_seconds()>=FRESH_SECONDS):raise HTTPException(409,'Validation expired or current page changed')
    if con.execute("SELECT 1 FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED')").fetchone():raise HTTPException(409,'Active content command')
    record={'released_at':now(),'validated_url':current['current_url'],'validation_evidence':json.loads(row['samples_json']),
        'previous_incident':incident,'validation_id':ident,'release_type':'EXPLICIT_OPERATOR_ACTION'}
    history=state(con,'browser_security_history').get('items',[])
    put(con,'browser_security_history',{'items':[*history,{**incident,**record}]})
    put(con,'browser_security_clearance',incident);put(con,'browser_security_stop',{})
    put(con,'safe_collection_guard',{'enabled':True,'validation_id':ident})
    con.execute('UPDATE safe_recovery_checks SET release_json=? WHERE id=?',(encoded(record),ident))
    return record


def start(con,ident,queries,stage=1):
    """Deprecated Stage adapter; use app.discovery_runner.DiscoveryRunner."""
    from .discovery_runner import DiscoveryRunner
    return DiscoveryRunner.start(con,ident,queries,stage)



def advance(con,batch):
    """Deprecated Stage adapter; use app.discovery_runner.DiscoveryRunner."""
    from .discovery_runner import DiscoveryRunner
    return DiscoveryRunner.advance(con,batch)



def command_allowed(con,row):
    """Deprecated adapter to canonical Safety/DiscoveryRunner policy."""
    from .discovery_runner import DiscoveryRunner
    return DiscoveryRunner.command_allowed(con,row)



def runtime_used(con,batch):
    """Deprecated adapter to canonical Safety/DiscoveryRunner policy."""
    from .discovery_runner import DiscoveryRunner
    return DiscoveryRunner.runtime_used(con,batch)



def collection_check(con,batch):
    """Deprecated adapter to canonical Safety/DiscoveryRunner policy."""
    from .discovery_runner import DiscoveryRunner
    return DiscoveryRunner.collection_check(con,batch)



def authorize_healthy_stage1(con,ident,extension_id):
    """Explicit search-only authorization after a new passive check; clears no latch."""
    row=con.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(ident,)).fetchone()
    if not row or row['status']!='HEALTHY' or row['release_json']:raise HTTPException(409,'New HEALTHY passive check required')
    if state(con,'browser_security_stop').get('reason') or state(con,'target_security_pending').get('items'):raise HTTPException(409,'Security is blocked or pending')
    bridge=state(con,'tiktok_bridge');current=health(bridge,extension_id,row['build_id'])
    previous=json.loads(row['evidence_json'])
    if current['status']!='HEALTHY' or len(json.loads(row['samples_json']))<CHECK_SAMPLES or any(current.get(k)!=previous.get(k) for k in ('current_url','tab_id')) or (datetime.now(timezone.utc)-datetime.fromisoformat(row['validated_at'])).total_seconds()>=FRESH_SECONDS:raise HTTPException(409,'Fresh matching healthy home/search required')
    if con.execute("SELECT 1 FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED')").fetchone():raise HTTPException(409,'Active content command')
    record={'authorization_type':'SEARCH_ONLY_STAGE1','authorized_at':now(),'validated_url':current['current_url'],'validation_evidence':json.loads(row['samples_json'])}
    con.execute('UPDATE safe_recovery_checks SET release_json=? WHERE id=?',(encoded(record),ident))
    put(con,'safe_collection_guard',{'enabled':True,'validation_id':ident})
    return record


def authorize_stage2(con,ident,fresh,queries,extension_id):
    """Deprecated Stage adapter; use app.discovery_runner.DiscoveryRunner."""
    from .discovery_runner import DiscoveryRunner
    return DiscoveryRunner.authorize_stage2(con,ident,fresh,queries,extension_id)



def resume_stage2(con,batch_id,fresh,extension_id):
    """Deprecated Stage adapter; use app.discovery_runner.DiscoveryRunner."""
    from .discovery_runner import DiscoveryRunner
    return DiscoveryRunner.resume_stage2(con,batch_id,fresh,extension_id)



def finish(con,row,status,capture,inserted=0,updated=0):
    """Deprecated command adapter; use app.discovery_runner.DiscoveryRunner."""
    from .discovery_runner import DiscoveryRunner
    return DiscoveryRunner.finish(con,row,status,capture,inserted,updated)



def post_capture(con,command_id):
    """Deprecated adapter to canonical Safety/DiscoveryRunner policy."""
    from .discovery_runner import DiscoveryRunner
    return DiscoveryRunner.post_capture(con,command_id)



def summary(con):
    migrate(con);bridge=state(con,'tiktok_bridge')
    check=con.execute('SELECT * FROM safe_recovery_checks ORDER BY created_at DESC LIMIT 1').fetchone()
    batch=con.execute('SELECT * FROM safe_collection_batches ORDER BY created_at DESC LIMIT 1').fetchone()
    healthy=con.execute("SELECT * FROM safe_recovery_checks WHERE status='HEALTHY' ORDER BY validated_at DESC LIMIT 1").fetchone()
    fresh=health(bridge,bridge.get('extension_id',''),bridge.get('build_id',''))['companion_connected']
    discovery_run=__import__('app.discovery_runner',fromlist=['DiscoveryRunner']).DiscoveryRunner.report(con,batch['id']) if batch else None
    return {'companion':fresh,'discovery_run':discovery_run,
        'session':bridge.get('tiktok_session_status','unconfirmed') if fresh else 'unconfirmed','page':bridge.get('current_page_status','unknown') if fresh else 'unknown',
        'security_stop':state(con,'browser_security_stop'),'last_safe_validation':dict(healthy) if healthy else None,
        'last_check':dict(check) if check else None,'last_collection':dict(batch) if batch else None,
        'new_videos':batch['new_videos'] if batch else 0,'last_stop_reason':state(con,'browser_security_stop').get('reason') or (batch['stop_reason'] if batch else None)}
