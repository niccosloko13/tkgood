"""Persistent target quarantine. Unknown general health holds collection, never retries.

Only a fresh, complete, authenticated home/search observation AFTER the failure
can isolate it. Challenge and three distinct targets within ten minutes are global.
"""
import json
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from . import db
from .safe_collection import state, put, health, now

WINDOW_SECONDS = 600
TARGET_LIMIT = 3
router = APIRouter()


def target(url):
    try:
        u = urlsplit(url)
        if u.scheme != 'https' or u.hostname not in ('www.tiktok.com', 'tiktok.com') or u.port not in (None,443) or u.username or u.password:
            return None
        path = u.path.rstrip('/').lower()
        kind = 'VIDEO' if re.fullmatch(r'/@[A-Za-z0-9._]+/video/[0-9]+',path) else 'CREATOR' if re.fullmatch(r'/@[A-Za-z0-9._]+',path) else None
        return (kind, 'https://www.tiktok.com'+path) if kind else None
    except ValueError:
        return None


def migrate(con):
    con.execute('''CREATE TABLE IF NOT EXISTS blocked_targets (
      target_type TEXT NOT NULL,url TEXT PRIMARY KEY,reason TEXT NOT NULL,
      first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,attempt_count INTEGER NOT NULL,
      status TEXT NOT NULL CHECK(status='BLOCKED'))''')
    con.execute('''CREATE TABLE IF NOT EXISTS target_block_events (
      url TEXT NOT NULL,observed_at TEXT NOT NULL,received_at TEXT NOT NULL,
      PRIMARY KEY(url,observed_at))''')
    con.execute('''CREATE TABLE IF NOT EXISTS temporary_target_quarantines (
      url TEXT PRIMARY KEY,target_type TEXT NOT NULL,status TEXT NOT NULL,
      reason TEXT NOT NULL,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,
      context_run_id INTEGER NOT NULL,context_command_id INTEGER NOT NULL,incident_json TEXT NOT NULL,
      note TEXT NOT NULL)''')


def blocked(con,url):
    item=target(url)
    if not item:return False
    migrate(con)
    if item[0]=='VIDEO':
        key='%/video/'+item[1].rsplit('/',1)[1]
        return bool(con.execute("SELECT 1 FROM blocked_targets WHERE target_type='VIDEO' AND url LIKE ? AND status='BLOCKED'",(key,)).fetchone() or con.execute("SELECT 1 FROM temporary_target_quarantines WHERE target_type='VIDEO' AND url LIKE ? AND status='TEMPORARILY_QUARANTINED'",(key,)).fetchone())
    return bool(con.execute("SELECT 1 FROM blocked_targets WHERE url=? AND status='BLOCKED'",(item[1],)).fetchone() or con.execute("SELECT 1 FROM temporary_target_quarantines WHERE url=? AND status='TEMPORARILY_QUARANTINED'",(item[1],)).fetchone())


def rows(con):
    migrate(con)
    result={r['url']:dict(r) for r in con.execute('SELECT * FROM blocked_targets ORDER BY first_seen,url')}
    for row in con.execute("SELECT * FROM temporary_target_quarantines WHERE status='TEMPORARILY_QUARANTINED'"):
        result.setdefault(row['url'],{**dict(row),'attempt_count':0})
    return sorted(result.values(),key=lambda r:(r['first_seen'],r['url']))


def quarantine_challenge_context(con,run_id):
    """Association only: do not create an HTTP-403 event or assert causality."""
    migrate(con)
    run=con.execute('SELECT * FROM selective_runs WHERE id=?',(run_id,)).fetchone()
    if not run or run['status'] not in ('STOPPED','INTERRUPTED'):raise HTTPException(409,'Stopped selective pilot required')
    command=con.execute("SELECT * FROM bridge_commands WHERE json_extract(options_json,'$.selective_run_id')=? AND status='FAILED' ORDER BY id LIMIT 1",(run_id,)).fetchone()
    context=None
    if not command or not re.search(r'captcha|challenge',command['detail'],re.I):
        # A detail read can have completed before its required passive post-check
        # sees the challenge. The durable context records that exact association
        # without claiming target causality.
        context=con.execute("SELECT * FROM navigation_challenge_contexts WHERE event_key=?",(f'selective:{run_id}:individual-navigation-challenge',)).fetchone()
        if not context:raise HTTPException(409,'Recorded challenge context required')
        source=json.loads(context['source_json'])
        recorded=source.get('incident',{})
        current=state(con,'browser_security_stop')
        if recorded != current:raise HTTPException(409,'Challenge incident changed')
        item=target(context['target'])
        command_id=source.get('command_id')
    else:
        item=target(command['query'])
        command_id=command['id']
    if not item:raise HTTPException(409,'Public target context required')
    incident=state(con,'browser_security_stop')
    existing=con.execute('SELECT * FROM temporary_target_quarantines WHERE url=?',(item[1],)).fetchone()
    if not existing:
        stamp=now()
        con.execute("INSERT INTO temporary_target_quarantines VALUES (?,?,'TEMPORARILY_QUARANTINED','CHALLENGE_TRIGGER_CONTEXT',?,?,?,?,?,?)",(item[1],item[0],stamp,stamp,run_id,command_id,json.dumps(incident,sort_keys=True),'Associated with the moment of challenge; not evidence this target technically caused CAPTCHA. No automatic expiry or reopen.'))
    return dict(con.execute('SELECT * FROM temporary_target_quarantines WHERE url=?',(item[1],)).fetchone())


def quarantine(con,url,observed_at):
    item=target(url)
    if not item:raise ValueError('Not an individual public target')
    migrate(con)
    fresh=con.execute('INSERT OR IGNORE INTO target_block_events VALUES (?,?,?)',(item[1],observed_at,now())).rowcount
    if fresh:
        con.execute('''INSERT INTO blocked_targets VALUES (?,?,'HTTP_403',?,?,1,'BLOCKED')
          ON CONFLICT(url) DO UPDATE SET first_seen=min(first_seen,excluded.first_seen),last_seen=max(last_seen,excluded.last_seen),attempt_count=attempt_count+1''',
          (item[0],item[1],observed_at,observed_at))
    return item[1]


def circuit_open(con):
    cutoff=(datetime.now(timezone.utc)-timedelta(seconds=WINDOW_SECONDS)).isoformat()
    identities=set()
    for row in con.execute('SELECT DISTINCT url FROM target_block_events WHERE received_at>=?',(cutoff,)):
        item=target(row[0])
        if item:identities.add((item[0],item[1].rsplit('/',1)[1] if item[0]=='VIDEO' else item[1]))
    return len(identities)>=TARGET_LIMIT


def general_block_reason(bridge):
    """Consume existing detector evidence; unknown/transitional DOM remains a hold."""
    from .safe_collection import healthy_route
    from .safety import SafetyGate
    try:path=urlsplit(bridge.get('current_url','')).path
    except ValueError:path=''
    # The bridge's security_stop is a persisted latch echoed between heartbeats,
    # not evidence that this document is currently blocked. Current DOM/page
    # signals are evaluated here; latch ownership stays in browser_safety.
    evidence={**bridge,'security_stop':None,'current_page_status':'challenge' if re.match(r'^/(challenge|captcha|verify)(/|$)',path,re.I) else bridge.get('current_page_status')}
    decision=SafetyGate.observation(evidence)
    if decision.page=='CHALLENGE':return 'GLOBAL_BLOCK: challenge/captcha/verification'
    if healthy_route(bridge.get('current_url','')) and bridge.get('current_page_status')=='http_403':
        return 'GLOBAL_BLOCK: home/search HTTP 403'
    if bridge.get('page_ready_state')=='complete' and (decision.page=='LOGGED_OUT' or re.match(r'^/login(/|$)',path,re.I)):
        return 'GLOBAL_BLOCK: session degraded/login required'
    return None


def classify_pending(con,bridge):
    pending=state(con,'target_security_pending')
    if not pending.get('items'):return None
    migrate(con)
    if circuit_open(con):return 'GLOBAL_BLOCK: three distinct targets returned HTTP 403 within 10 minutes'
    # Do not use a previous successful page to justify continued navigation.
    latest=max(x['observed_at'] for x in pending['items'])
    try:
        if datetime.fromisoformat(bridge.get('last_seen','').replace('Z','+00:00')) < datetime.fromisoformat(latest.replace('Z','+00:00')):return None
    except ValueError:return None
    evidence=health(bridge,bridge.get('extension_id',''),bridge.get('build_id',''))
    if re.search(r'captcha|challenge|verify.*human',bridge.get('security_stop') or '',re.I):
        return 'GLOBAL_BLOCK: current challenge after target HTTP 403'
    from .safe_collection import healthy_route
    if evidence['status']=='CHALLENGE' or (healthy_route(bridge.get('current_url','')) and evidence['status']=='BLOCKED'):
        return 'GLOBAL_BLOCK: home/search or current page security blocker after target HTTP 403'
    if healthy_route(bridge.get('current_url','')) and evidence['heartbeat_fresh'] and bridge.get('page_ready_state')=='complete' and bridge.get('tiktok_session_status') in ('unconfirmed','login_required'):
        return 'GLOBAL_BLOCK: session degraded after target HTTP 403'
    if evidence['status']!='HEALTHY':return None
    current=state(con,'browser_security_stop')
    # Only migrate the exact target-403 incident, never a global/challenge latch.
    def same_time(a,b):
        try:return datetime.fromisoformat(a.replace('Z','+00:00'))==datetime.fromisoformat(b.replace('Z','+00:00'))
        except (ValueError,AttributeError):return False
    matching=next((x for x in pending['items'] if current.get('reason')=='HTTP 403: '+x['url'] and same_time(current.get('observed_at'),x['observed_at'])),None)
    if current.get('reason') and not matching:return None
    history=state(con,'browser_security_history').get('items',[])
    for item in pending['items']:
        history.append({**item,'classification':'TARGET_BLOCK','classified_at':now(),'healthy_url':bridge['current_url'],'healthy_observed_at':bridge['last_seen']})
    put(con,'browser_security_history',{'items':history})
    if matching:
        put(con,'browser_security_clearance',current)
        put(con,'browser_security_stop',{})
    put(con,'target_security_pending',{})
    return None


def report_403(url,observed_at):
    from .browser_safety import stop
    item=target(url)
    if not item:
        stop('HTTP 403: '+safe_route(url),observed_at)
        return {'classification':'GLOBAL_BLOCK','security_stop':db.get_state('browser_security_stop',{})}
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        canonical=quarantine(con,url,observed_at)
        pending=state(con,'target_security_pending').get('items',[])
        event={'url':canonical,'observed_at':observed_at}
        if event not in pending:pending.append(event)
        put(con,'target_security_pending',{'items':pending})
        reason=classify_pending(con,state(con,'tiktok_bridge'))
        waiting=bool(state(con,'target_security_pending').get('items'))
        targets=rows(con)
    if reason:stop(reason,now())
    latch=db.get_state('browser_security_stop',{})
    return {'classification':'GLOBAL_BLOCK' if latch.get('reason') else 'TARGET_PENDING_HEALTH' if waiting else 'TARGET_BLOCK',
            'security_stop':latch,'blocked_targets':targets,'target_security_pending':waiting}


def safe_route(url):
    try:
        u=urlsplit(url)
        return f'{u.scheme}://{u.hostname or ""}{u.path}'[:400]
    except ValueError:return '[invalid route]'


class TargetFailure(BaseModel):
    model_config=ConfigDict(extra='forbid')
    extension_id:str=Field(min_length=1,max_length=128)
    url:str=Field(max_length=2048)
    observed_at:str=Field(max_length=64)


@router.post('/api/bridge/target-403')
def target_failure(payload:TargetFailure):
    if db.get_state('tiktok_bridge',{}).get('extension_id')!=payload.extension_id:raise HTTPException(403,'Companion identity mismatch')
    try:
        stamp=datetime.fromisoformat(payload.observed_at.replace('Z','+00:00'))
        if stamp.tzinfo is None:raise ValueError()
    except ValueError:raise HTTPException(422,'Timezone-aware observation required')
    return report_403(payload.url,stamp.astimezone(timezone.utc).isoformat())


@router.get('/api/bridge/blocked-targets')
def blocked_targets():
    with db.connect() as con:
        return {'items':rows(con),'pending':bool(state(con,'target_security_pending').get('items'))}
