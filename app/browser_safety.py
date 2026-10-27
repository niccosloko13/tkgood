"""Persistent stop latch; only explicit local operator review can clear it."""
from datetime import datetime, timezone
import json
import re
from . import db


def authenticated_account_evidence(bridge):
    """Independent live account families. Does not inspect the security latch."""
    from .safety import authenticated_account_evidence as canonical
    return canonical(bridge)


def failed_video_url(record):
    match=re.fullmatch(r'HTTP 403: (https://www\.tiktok\.com/@[A-Za-z0-9._]+/video/[0-9]+)',record.get('reason',''))
    return match.group(1) if match else None


def stop(reason, observed_at=None):
    previous=db.get_state('browser_security_stop', {})
    if previous.get('observed_at') and observed_at:
        try:
            if datetime.fromisoformat(observed_at.replace('Z','+00:00')) <= datetime.fromisoformat(previous['observed_at'].replace('Z','+00:00')):
                return previous
        except ValueError:
            return previous
    if previous.get('reason') and (not observed_at or observed_at==previous.get('observed_at')):
        return previous
    if previous.get('reason'):
        history=db.get_state('browser_security_history',{}).get('items',[])
        db.set_state('browser_security_history',{'items':[*history,previous]})
    record={'reason':reason[:500], 'observed_at':observed_at or datetime.now(timezone.utc).isoformat()}
    db.set_state('browser_security_stop',record)
    with db.connect() as con:
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='safe_collection_batches'").fetchone():
            con.execute("UPDATE safe_collection_batches SET status='BLOCKED',stop_reason=?,completed_at=? WHERE status IN ('READY','PENDING','PAUSED')",(reason[:500],record['observed_at']))
        for row in con.execute("SELECT id,type FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED')").fetchall():
            if row['type']=='DISCOVER_MORE_RESULTS':
                from .discovery import session_for,finish
                finish(con,session_for(con,row['id']),'security_challenge')
            con.execute("UPDATE bridge_commands SET status='FAILED',detail=?,updated_at=? WHERE id=?",
                        ('Security stop: '+reason[:500],record['observed_at'],row['id']))
    db.log_event('security_stop',reason[:500],'ERROR')
    return record


def clear_reviewed_stop(con, command_id, extension_id):
    """Explicit local operator action; never called by a heartbeat or collector."""
    from fastapi import HTTPException
    def state(key):
        row=con.execute('SELECT value_json FROM system_state WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else {}
    current=state('browser_security_stop')
    job=con.execute('SELECT * FROM dev_commands WHERE id=?',(command_id,)).fetchone()
    if not job or job['type']!='DEV_VALIDATE_TIKTOK_HOME' or job['status']!='SUCCEEDED':
        raise HTTPException(409,'A successful explicit home validation is required')
    expected=json.loads(job['options_json']).get('incident',{})
    if current!=expected or not failed_video_url(current):
        raise HTTPException(409,'Security incident changed or is not a historical video HTTP 403')
    bridge=state('tiktok_bridge')
    now=datetime.now(timezone.utc)
    try:
        seen=datetime.fromisoformat(bridge['last_seen'])
        valid=0 <= (now-seen).total_seconds() < 15 and seen >= datetime.fromisoformat(job['created_at'])
    except (KeyError,ValueError,TypeError):valid=False
    if not (valid and bridge.get('extension_id')==extension_id and bridge.get('build_id')==job['expected_build'] and
            bridge.get('current_url')=='https://www.tiktok.com/' and bridge.get('current_page_status')=='healthy' and
            bridge.get('page_ready_state')=='complete' and
            bridge.get('tiktok_session_status')=='confirmed' and
            authenticated_account_evidence(bridge)):
        raise HTTPException(409,'Fresh authenticated healthy home evidence is required')
    def put(key,value):
        con.execute('INSERT INTO system_state(key,value_json,updated_at) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at',
                    (key,json.dumps(value),now.isoformat()))
    history=state('browser_security_history').get('items',[])
    put('browser_security_history',{'items':[*history,{**current,'cleared_at':now.isoformat(),'validation_command_id':command_id,'page_failure':'isolated_403'}]})
    put('browser_security_clearance',current)
    put('browser_security_stop',{})
    con.execute('INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)',
                (now.isoformat(),'INFO','security_recovery','Reviewed historical video HTTP 403 cleared after authenticated home validation: '+failed_video_url(current)))
    return {'ok':True,'page_failure':'isolated_403','failed_url':failed_video_url(current)}
