"""Local-only persistent work queue. No browser commands or remote retries."""
import hashlib
import json
import uuid
import threading
from datetime import datetime, timezone, timedelta
from .intelligence_decisions import settings


def now():
    return datetime.now(timezone.utc).isoformat()


def migrate(con):
    con.executescript('''
    CREATE TABLE IF NOT EXISTS intelligence_jobs (
      id INTEGER PRIMARY KEY, job_type TEXT NOT NULL, target TEXT NOT NULL,
      fingerprint TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL,
      attempt_count INTEGER NOT NULL DEFAULT 0, reason_code TEXT, last_error TEXT,
      created_at TEXT NOT NULL, last_attempt TEXT, available_at TEXT NOT NULL,
      lease_token TEXT, lease_until TEXT, processing_ms REAL,
      UNIQUE(job_type,target,fingerprint));
    CREATE TABLE IF NOT EXISTS intelligence_job_history (
      id INTEGER PRIMARY KEY,job_id INTEGER NOT NULL REFERENCES intelligence_jobs(id),
      status TEXT NOT NULL,reason_code TEXT,observed_at TEXT NOT NULL);
    ''')
    if 'failure_class' not in {r[1] for r in con.execute('PRAGMA table_info(intelligence_jobs)')}:
        con.execute('ALTER TABLE intelligence_jobs ADD COLUMN failure_class TEXT')
    if 'resource_wait_count' not in {r[1] for r in con.execute('PRAGMA table_info(intelligence_jobs)')}:
        con.execute('ALTER TABLE intelligence_jobs ADD COLUMN resource_wait_count INTEGER NOT NULL DEFAULT 0')


def enqueue(con, job_type, target, payload):
    if job_type not in ('identity', 'embedding', 'index_rebuild','visual_identity'):
        raise ValueError('Local intelligence job type required')
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    fingerprint = hashlib.sha256(data.encode()).hexdigest()
    for old in con.execute("SELECT id,fingerprint,payload_json FROM intelligence_jobs WHERE job_type=? AND target=? AND status='queued'",(job_type,str(target))).fetchall():
        prior=json.loads(old['payload_json'])
        if old['fingerprint']!=fingerprint and bool(prior.get('with_embeddings'))==bool(payload.get('with_embeddings')):
            con.execute("UPDATE intelligence_jobs SET status='superseded',reason_code='INPUT_SUPERSEDED' WHERE id=?",(old['id'],))
            con.execute('INSERT INTO intelligence_job_history(job_id,status,reason_code,observed_at) VALUES (?,?,?,?)',(old['id'],'superseded','INPUT_SUPERSEDED',now()))
    con.execute('''INSERT OR IGNORE INTO intelligence_jobs
        (job_type,target,fingerprint,payload_json,status,created_at,available_at)
        VALUES (?,?,?,?,'queued',?,?)''', (job_type,str(target),fingerprint,data,now(),now()))
    return con.execute('SELECT id FROM intelligence_jobs WHERE job_type=? AND target=? AND fingerprint=?',
                       (job_type,str(target),fingerprint)).fetchone()[0]


def claim(con,embedding_mode=None,job_id=None):
    # Expired work gets a bounded retry, never a second concurrent owner.
    timestamp = now()
    p = settings()['jobs']
    con.execute("UPDATE intelligence_jobs SET status=CASE WHEN attempt_count-resource_wait_count>=? THEN 'dead-letter' ELSE 'queued' END, reason_code='LEASE_EXPIRED',lease_token=NULL WHERE status='processing' AND lease_until<?", (p['max_attempts'],timestamp))
    lane=''
    if embedding_mode is False:lane=" AND job_type='identity' AND coalesce(json_extract(payload_json,'$.with_embeddings'),0)=0"
    if embedding_mode is True:lane=" AND (job_type IN ('embedding','index_rebuild') OR (job_type='identity' AND json_extract(payload_json,'$.with_embeddings')=1))"
    if job_id is not None:lane+=' AND id='+str(int(job_id))
    row = con.execute("SELECT * FROM intelligence_jobs WHERE status='queued' AND available_at<=?"+lane+" ORDER BY id LIMIT 1", (timestamp,)).fetchone()
    if not row:
        return None
    token = uuid.uuid4().hex
    until = (datetime.now(timezone.utc)+timedelta(seconds=p['lease_seconds'])).isoformat()
    changed = con.execute("UPDATE intelligence_jobs SET status='processing',attempt_count=attempt_count+1,last_attempt=?,lease_token=?,lease_until=? WHERE id=? AND status='queued'", (timestamp,token,until,row['id'])).rowcount
    if not changed:
        return None
    return dict(con.execute('SELECT * FROM intelligence_jobs WHERE id=?',(row['id'],)).fetchone())


def finish(con, job, status='completed', failure=None, reason=None, error=None, processing_ms=None):
    if failure not in (None,'TRANSIENT','PERMANENT','SECURITY_BLOCK','INSUFFICIENT_DATA'):
        raise ValueError('Unknown failure type')
    available = now()
    if failure == 'TRANSIENT':
        status = 'queued' if job['attempt_count']-job.get('resource_wait_count',0) < settings()['jobs']['max_attempts'] else 'dead-letter'
        available = (datetime.now(timezone.utc)+timedelta(seconds=settings()['jobs']['retry_seconds']*job['attempt_count'])).isoformat()
    elif failure == 'PERMANENT': status = 'dead-letter'
    elif failure == 'SECURITY_BLOCK': status = 'blocked'
    elif failure == 'INSUFFICIENT_DATA': status = 'unresolved'
    if status not in ('completed','auto','review','unresolved','queued','dead-letter','blocked'):
        raise ValueError('Invalid terminal status')
    changed = con.execute('''UPDATE intelligence_jobs SET status=?,reason_code=?,last_error=?,available_at=?,failure_class=?,
        lease_token=NULL,lease_until=NULL,processing_ms=? WHERE id=? AND status='processing' AND lease_token=?''',
        (status,reason or failure,error,available,failure,processing_ms,job['id'],job['lease_token'])).rowcount
    if changed != 1: raise ValueError('Stale job ownership')
    con.execute('INSERT INTO intelligence_job_history(job_id,status,reason_code,observed_at) VALUES (?,?,?,?)',
                (job['id'],status,reason or failure,now()))


def blocked_jobs(con):
    return [{**dict(r),'recoverable':r['failure_class'] not in ('PERMANENT','SECURITY_BLOCK')} for r in con.execute(
        "SELECT job_type,target,reason_code,attempt_count,last_error,last_attempt,status,failure_class FROM intelligence_jobs WHERE status IN ('dead-letter','blocked') ORDER BY id")]


def defer(con,job,error):
    """Resource admission is waiting, not a failed inference or permanent failure."""
    finish(con,job,status='queued',reason='RESOURCE_DEFER',error=error)
    due=(datetime.now(timezone.utc)+timedelta(seconds=settings()['resources']['cooldown_seconds'])).isoformat()
    con.execute("UPDATE intelligence_jobs SET failure_class='RESOURCE_WAIT',resource_wait_count=resource_wait_count+1,available_at=? WHERE id=?",(due,job['id']))


_launch_lock=threading.Lock()


def start_worker(task='intelligence-worker'):
    """Use the existing fixed-task launcher, never an arbitrary/background shell."""
    from pathlib import Path
    import subprocess
    import psutil
    from scripts.process_runtime import hidden_kwargs
    root=Path(__file__).resolve().parents[1]
    if task not in ('intelligence-worker','visual-identity-worker'):raise ValueError('Fixed intelligence task required')
    with _launch_lock:
        for path in (root/'.runtime/logs').glob('task-*.json'):
            try:record=json.loads(path.read_text(encoding='utf-8'))
            except (ValueError,OSError):continue
            if record.get('task')!=task or record.get('status') not in ('STARTING','RUNNING'):continue
            if record.get('pid') and psutil.pid_exists(record['pid']):return {'status':'running','task_id':record['id']}
            if record.get('status')=='STARTING' and (datetime.now(timezone.utc)-datetime.fromisoformat(record['created_at'])).total_seconds()<30:
                return {'status':'queued','task_id':record['id']}
        result=subprocess.run([str(root/'.venv/Scripts/python.exe'),str(root/'scripts/background_runner.py'),task],cwd=root,
                              stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10,**hidden_kwargs())
        if result.returncode:raise RuntimeError(result.stderr)
        return {'status':'queued','task_id':result.stdout.strip()}
