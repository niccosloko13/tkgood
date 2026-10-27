"""DEPRECATED Stage 2 compatibility CLI; policy/lifecycle/report live in DiscoveryRunner."""
import json
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dev_supervisor import Supervisor
from app import db,safe_collection as safe,target_safety
from app.category_intelligence import config

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'artifacts/controlled-stage2/run-20261025.json'
QUERIES=['home gadgets','home finds','useful home products','kitchen gadgets','cleaning gadgets']


def save(value):
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    temporary=REPORT.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2),encoding='utf-8');temporary.replace(REPORT)


def gate(con):
    # Consult quarantine before each command; never request a blocked individual.
    targets=target_safety.rows(con);bridge=safe.state(con,'tiktok_bridge')
    if safe.state(con,'browser_security_stop').get('reason'):raise RuntimeError('GLOBAL_SECURITY_EVENT')
    if safe.state(con,'target_security_pending').get('items'):raise RuntimeError('TARGET_HEALTH_PENDING')
    if safe.health(bridge,bridge.get('extension_id',''),bridge.get('build_id',''))['status']!='HEALTHY':raise RuntimeError('SESSION_OR_PAGE_NOT_HEALTHY')
    return targets


def reconcile(report):
    with db.connect() as con:
        bridge=safe.state(con,'tiktok_bridge');batch=con.execute('SELECT * FROM safe_collection_batches WHERE id=?',(report.get('batch_id',''),)).fetchone()
        metrics=[dict(r) for r in con.execute('SELECT * FROM safe_query_metrics WHERE batch_id=? ORDER BY command_id',(report.get('batch_id',''),))]
        observations=[dict(r) for r in con.execute('''SELECT o.* FROM search_observations o JOIN safe_query_metrics m ON o.capture_id='command:'||m.command_id WHERE m.batch_id=?''',(report.get('batch_id',''),))]
        creators={json.loads(r['fields_json']).get('creator_username') for r in observations};creators.discard(None);creators.discard('')
        snapshots=con.execute("SELECT count(*) FROM trend_snapshot_sources s JOIN search_observations o ON s.source_key='search_observations:'||o.id JOIN safe_query_metrics m ON o.capture_id='command:'||m.command_id WHERE m.batch_id=?",(report.get('batch_id',''),)).fetchone()[0]
        report.update(batch=dict(batch) if batch else None,query_metrics=metrics,queries_completed=sum(m['status']=='SUCCEEDED' for m in metrics),results=sum(m['results'] for m in metrics),new_videos=sum(m['new_videos'] for m in metrics),duplicates=sum(m['duplicates'] for m in metrics),blocked_targets_skipped=sum(m['blocked'] for m in metrics),invalid=sum(m['invalid'] for m in metrics),observations=len(observations),trend_snapshots=snapshots,unique_creators=len(creators),final_page=bridge.get('current_page_status'),session=bridge.get('tiktok_session_status'),global_security=safe.state(con,'browser_security_stop'),blocked_targets=target_safety.rows(con),final_url=bridge.get('current_url'))
        from app.discovery_runner import DiscoveryRunner
        if report.get('batch_id'):report['discovery_run']=DiscoveryRunner.report(con,report['batch_id'])
    save(report);return report


def main():
    if REPORT.exists():raise RuntimeError('Pilot intent already exists; no automatic retry')
    pack={q[0] for q in config('discovery_intelligence')['queries'] if q[1]=='home'}
    if not set(QUERIES)<=pack:raise RuntimeError('Query pack changed')
    with db.connect() as con:
        gate(con)
        passed=con.execute("SELECT validation_id FROM safe_collection_batches WHERE stage=1 AND status='SUCCEEDED' ORDER BY created_at DESC LIMIT 1").fetchone()
        if not passed:raise RuntimeError('Stage 1 success required')
        prior=passed['validation_id']
    s=Supervisor();check=s.request('/api/dev/safe-recovery/checks',{})
    deadline=time.monotonic()+35
    while check['status']=='PENDING' and time.monotonic()<deadline:
        time.sleep(1);check=s.request('/api/dev/safe-recovery/checks/'+check['id'])
    if check['status']!='HEALTHY':raise RuntimeError('Passive health check did not pass')
    authorization=s.request('/api/dev/safe-collection/authorize-stage2',{'validation_id':prior,'fresh_check_id':check['id'],'queries':QUERIES,'operator_reviewed':True})
    report={'queries':QUERIES,'pack_version':config('discovery_intelligence')['pack_version'],'authorization':authorization,'intents':[],'stage3_executed':False}
    # Persist intent before the first content POST. No response is ever replayed.
    save(report);stop_reason='UNCONFIRMED_OUTCOME'
    try:
        with db.connect() as con:gate(con)
        report['intents'].append({'query':QUERIES[0],'action':'START_STAGE2'});save(report)
        job=s.request('/api/dev/safe-collection',{'validation_id':prior,'stage':2,'queries':QUERIES})
        report['batch_id']=job['id'];report['commands']=[job['command_id']];save(report)
        while True:
            deadline=time.monotonic()+50
            while True:
                with db.connect() as con:
                    db.expire_commands(con)
                    row=con.execute('SELECT id,status,detail FROM bridge_commands WHERE id=?',(job['command_id'],)).fetchone()
                    command=dict(row)
                if command['status'] in ('SUCCEEDED','FAILED','EXPIRED'):break
                if time.monotonic()>=deadline:raise RuntimeError('UNCONFIRMED_COMMAND_OUTCOME_NO_RETRY')
                time.sleep(1)
            report=reconcile(report)
            if command['status']!='SUCCEEDED':stop_reason='COMMAND_FAILED_NO_RETRY: '+command['detail'];break
            if report['observations']!=report['trend_snapshots']:raise RuntimeError('TREND_SOURCE_COVERAGE_MISMATCH')
            if report['batch']['status']=='SUCCEEDED':stop_reason=report['batch']['stop_reason'];break
            with db.connect() as con:
                gate(con)
                elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(report['batch']['created_at'])).total_seconds()
                if elapsed>safe.MAX_RUNTIME_SECONDS-35:stop_reason='MAX_RUNTIME';break
            query=QUERIES[report['batch']['query_index']]
            report['intents'].append({'query':query,'action':'EXPLICIT_NEXT_QUERY'});save(report)
            job=s.request('/api/dev/safe-collection/'+report['batch_id']+'/next',{'operator_reviewed':True})
            report['commands'].append(job['command_id']);save(report)
    except Exception as error:
        stop_reason=str(error)
    finally:
        report['stop_reason']=stop_reason
        if report.get('batch_id'):
            with db.connect() as con:
                con.execute("UPDATE safe_collection_batches SET status='FAILED',stop_reason=?,completed_at=? WHERE id=? AND status IN ('READY','PAUSED')",(stop_reason,safe.now(),report['batch_id']))
        report=reconcile(report);print(json.dumps(report,indent=2),flush=True)
    return 0 if report['batch'] and report['batch']['status']=='SUCCEEDED' else 1


if __name__=='__main__':raise SystemExit(main())
