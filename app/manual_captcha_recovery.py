"""Explicit manual-CAPTCHA recovery and one next-HIGH permit. Never navigates."""
import json
import re
import time
from datetime import datetime,timezone,timedelta
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from . import db,safe_collection as safe,selective_enrichment as selective,target_safety
from .browser_safety import authenticated_account_evidence
from .dev_control import authorize

router=APIRouter()


def migrate(c):
    c.execute('''CREATE TABLE IF NOT EXISTS manual_captcha_recoveries (
      check_id TEXT PRIMARY KEY,parent_run_id INTEGER NOT NULL UNIQUE,record_json TEXT NOT NULL,
      released_at TEXT NOT NULL,child_run_id INTEGER)''')


def release(c,check_id,parent_run_id,extension_id):
    # Releasing a manually solved CAPTCHA archives an incident and permits the
    # existing narrow search-only guard. It is not a direct-reader action:
    # direct_video_enrichment may remain PAUSED indefinitely.
    migrate(c)
    old=c.execute('SELECT * FROM manual_captcha_recoveries WHERE check_id=?',(check_id,)).fetchone()
    if old:return {**json.loads(old['record_json']),'reused':True,'global_stop_active':bool(safe.state(c,'browser_security_stop').get('reason'))}
    check=c.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(check_id,)).fetchone()
    if not check or check['status']!='HEALTHY' or check['release_json'] or check['extension_id']!=extension_id:raise HTTPException(409,'New matching HEALTHY passive check required')
    current=safe.state(c,'browser_security_stop');bridge=safe.state(c,'tiktok_bridge')
    if current!=json.loads(check['incident_json']) or not re.search(r'captcha|challenge|verify.*human',current.get('reason',''),re.I):raise HTTPException(409,'Challenge incident changed or not eligible')
    evidence=safe.health(bridge,extension_id,check['build_id']);prior=json.loads(check['evidence_json']);samples=json.loads(check['samples_json'])
    if evidence['status']!='HEALTHY' or len(samples)<2 or any(evidence.get(k)!=prior.get(k) for k in ('current_url','tab_id')) or (datetime.now(timezone.utc)-datetime.fromisoformat(check['validated_at'])).total_seconds()>=15:raise HTTPException(409,'Fresh matching healthy page and confirmed session required')
    if safe.state(c,'target_security_pending').get('items'):raise HTTPException(409,'Unresolved target-health hold')
    from .dev_control import active_operations
    if any(active_operations(c).values()):raise HTTPException(409,'Active operation; release refused')
    context=target_safety.quarantine_challenge_context(c,parent_run_id)
    if json.loads(context['incident_json'])!=current:raise HTTPException(409,'Quarantined context does not match the reviewed incident')
    stamp=safe.now();record={'release_type':'EXPLICIT_MANUAL_CAPTCHA_RECOVERY','released_at':stamp,'validation_id':check_id,'parent_run_id':parent_run_id,'previous_incident':current,'validation_samples':samples,'validated_url':evidence['current_url'],'temporary_quarantine':context,'reused':False}
    history=safe.state(c,'browser_security_history').get('items',[])
    safe.put(c,'browser_security_history',{'items':[*history,{**current,**record}]})
    safe.put(c,'browser_security_clearance',current);safe.put(c,'browser_security_stop',{})
    c.execute('UPDATE safe_recovery_checks SET release_json=? WHERE id=?',(safe.encoded(record),check_id))
    c.execute('INSERT INTO manual_captcha_recoveries VALUES (?,?,?,?,NULL)',(check_id,parent_run_id,safe.encoded(record),stamp))
    c.execute("UPDATE selective_items SET status='TEMPORARILY_QUARANTINED' WHERE run_id=? AND video_id=(SELECT current_video FROM selective_runs WHERE id=?)",(parent_run_id,parent_run_id))
    return record


def next_high(c,check_id,extension_id):
    recovery=c.execute('SELECT * FROM manual_captcha_recoveries WHERE check_id=?',(check_id,)).fetchone()
    if not recovery:raise HTTPException(409,'Explicit manual recovery release required')
    if recovery['child_run_id']:return {'id':recovery['child_run_id'],'reused':True}
    check=c.execute('SELECT * FROM safe_recovery_checks WHERE id=?',(check_id,)).fetchone()
    if check['extension_id']!=extension_id or safe.state(c,'tiktok_bridge').get('build_id')!=check['build_id']:raise HTTPException(409,'Companion identity/build changed')
    from .dev_control import active_operations
    if any(active_operations(c).values()) or selective.active(c):raise HTTPException(409,'Another operation owns the tab')
    selective._guard(c,False)
    parent=c.execute('SELECT * FROM selective_runs WHERE id=?',(recovery['parent_run_id'],)).fetchone()
    chosen=None
    for vid in json.loads(parent['selected_json']):
        item=c.execute('SELECT * FROM selective_items WHERE run_id=? AND video_id=?',(parent['id'],vid)).fetchone()
        v=c.execute('SELECT * FROM videos WHERE id=?',(vid,)).fetchone()
        if item['status']=='SELECTED' and json.loads(item['priority_json'])['priority']=='HIGH' and not target_safety.blocked(c,v['canonical_url']):chosen=(item,v);break
    if not chosen:raise HTTPException(409,'NO_UNPROCESSED_HIGH')
    item,video=chosen;stamp=safe.now();deadline=(datetime.now(timezone.utc)+timedelta(seconds=min(selective.RUNTIME,300))).isoformat()
    ident=c.execute("INSERT INTO selective_runs(pilot_key,status,created_at,deadline_at,selected_json) VALUES (?,'RUNNING',?,?,?)",('manual-captcha-next:'+str(parent['id']),stamp,deadline,safe.encoded([video['id']]))).lastrowid
    c.execute("INSERT INTO selective_items VALUES (?,?,?,?,NULL,'SELECTED','{}')",(ident,video['id'],item['priority_json'],selective.encode(selective.intelligence(c,video['id']))))
    checkpoint={'max_candidates':1,'manual_recovery_check_id':check_id,'parent_run_id':parent['id'],'unselected_digest_before':selective.unselected_digest(c,[video['id']]),'priority_version':selective.VERSION,'scope':'one next unprocessed frozen HIGH after explicit manual recovery'}
    c.execute('UPDATE selective_runs SET checkpoint_json=? WHERE id=?',(safe.encoded(checkpoint),ident))
    c.execute('UPDATE manual_captcha_recoveries SET child_run_id=? WHERE check_id=?',(ident,check_id))
    return {'id':ident,'video_id':video['id'],'video_url':video['canonical_url'],'max_candidates':1,'reused':False}


class CheckFailure(RuntimeError):
    def __init__(self,reason,samples):super().__init__(reason);self.samples=samples


def checkpoint(vid,label,after=None):
    """Only existing authenticated heartbeat observations; no browser command."""
    deadline=time.monotonic()+25;samples=[];seen=None;consecutive=0
    while time.monotonic()<deadline:
        with db.connect() as c:
            bridge=safe.state(c,'tiktok_bridge');stop=safe.state(c,'browser_security_stop')
            if stop.get('reason'):raise CheckFailure('GLOBAL_SECURITY_EVENT',samples)
            if safe.state(c,'target_security_pending').get('items'):raise CheckFailure('TARGET_HEALTH_PENDING',samples)
            session=bridge.get('tiktok_session_status');page=bridge.get('current_page_status')
            hard=page=='challenge' or session=='login_required' or bridge.get('session_signals',{}).get('logged_out_cta_present') is True or re.search(r'captcha|challenge|verify.*human',bridge.get('live_page_blocker') or '',re.I)
            if page=='http_403':failure_url=bridge.get('current_url')
            else:failure_url=None
            expected=c.execute('SELECT canonical_url FROM videos WHERE id=?',(vid,)).fetchone()[0]
        if hard:
            from .browser_safety import stop as global_stop
            global_stop('GLOBAL_BLOCK: current challenge or confirmed logout during passive check',safe.now())
            raise CheckFailure('GLOBAL_SECURITY_EVENT',samples)
        if failure_url:
            target_safety.report_403(failure_url,bridge.get('last_seen') or safe.now());raise CheckFailure('HTTP_403_NO_RETRY',samples)
        stamp=bridge.get('last_seen');eligible=bool(stamp and (not after or stamp>=after))
        try:fresh=0<=(datetime.now(timezone.utc)-datetime.fromisoformat(stamp)).total_seconds()<15
        except (TypeError,ValueError):fresh=False
        actual=target_safety.target(bridge.get('current_url',''));wanted=target_safety.target(expected)
        route=label=='pre' or (actual and wanted and actual[0]=='VIDEO' and actual[1].rsplit('/',1)[1]==wanted[1].rsplit('/',1)[1])
        healthy=eligible and fresh and route and bridge.get('page_ready_state')=='complete' and page=='healthy' and session=='confirmed' and authenticated_account_evidence(bridge)
        if eligible and stamp!=seen:
            seen=stamp;consecutive=consecutive+1 if healthy else 0
            samples.append({'observed_at':stamp,'page':page,'session':session,'ready_state':bridge.get('page_ready_state'),'state':'HEALTHY_CONFIRMED' if healthy else 'TRANSIENT_LOADING','consecutive':consecutive})
            if consecutive>=2:return {'status':'HEALTHY','samples':samples,'final_page':page,'session':session}
        time.sleep(1)
    raise CheckFailure('SESSION_NOT_STABLE',samples)


class ReleaseRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    check_id:str=Field(pattern=r'^[a-f0-9]{32}$')
    parent_run_id:int=Field(gt=0)
    operator_reviewed:Literal[True]

class NextRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    operator_reviewed:Literal[True]

@router.post('/api/dev/manual-captcha/release')
def release_api(body:ReleaseRequest,config=Depends(authorize)):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE');return release(c,body.check_id,body.parent_run_id,config['extension_id'])

@router.post('/api/dev/manual-captcha/{check_id}/next-high')
def next_api(check_id:str,body:NextRequest,config=Depends(authorize)):
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE');return next_high(c,check_id,config['extension_id'])
