"""DEPRECATED Stage 1 compatibility CLI; policy/lifecycle/report live in DiscoveryRunner."""
import json
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dev_supervisor import Supervisor
from app import db,target_safety
from app.safe_collection import state,health

REPORT=Path(__file__).resolve().parents[1]/'artifacts/target-quarantine/stage1.json'


def save(value):
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(value,indent=2),encoding='utf-8')


def collect_report(report):
    """Read-only reconciliation of the one saved command; never submits work."""
    job=report['job']
    with db.connect() as con:
        command=dict(con.execute('SELECT id,status,detail FROM bridge_commands WHERE id=?',(job['command_id'],)).fetchone())
        bridge=state(con,'tiktok_bridge');batch=dict(con.execute('SELECT * FROM safe_collection_batches WHERE id=?',(job['id'],)).fetchone())
        refs=[dict(r) for r in con.execute('SELECT o.video_id,v.canonical_url AS video_url FROM search_observations o JOIN videos v ON v.id=o.video_id WHERE o.capture_id=?',(f"command:{job['command_id']}",))]
        report.update(command=command,batch=batch,actual_search_url=bridge.get('current_url'),results=len(refs),observations=len(refs),new_videos=batch['new_videos'],duplicates=batch['duplicates'],trend_snapshots=batch['snapshots'],
                      skipped_targets=[x for x in refs if target_safety.blocked(con,x['video_url'])],blocked_targets=target_safety.rows(con),global_security=state(con,'browser_security_stop'),target_security_pending=state(con,'target_security_pending'),
                      final_page=bridge.get('current_page_status'),final_session=bridge.get('tiktok_session_status'),stage2_executed=False)
        from app.discovery_runner import DiscoveryRunner
        report['discovery_run']=DiscoveryRunner.report(con,job['id'])
    save(report);return report


def main():
    global REPORT
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',type=str)
    args=parser.parse_args()
    if args.run_id:
        import re
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',args.run_id):parser.error('Invalid run ID')
        REPORT=REPORT.with_name('stage1-'+args.run_id+'.json')
    if REPORT.exists():raise RuntimeError('Prior pilot record exists; no retry permitted')
    supervisor=Supervisor()
    with db.connect() as con:
        bridge=state(con,'tiktok_bridge')
        if state(con,'browser_security_stop').get('reason') or state(con,'target_security_pending').get('items') or health(bridge,bridge.get('extension_id',''),bridge.get('build_id',''))['status']!='HEALTHY':
            raise RuntimeError('Fresh confirmed healthy home/search and no security block required')
    check=supervisor.request('/api/dev/safe-recovery/checks',{})
    deadline=time.monotonic()+35
    while check['status']=='PENDING' and time.monotonic()<deadline:
        time.sleep(1)
        check=supervisor.request('/api/dev/safe-recovery/checks/'+check['id'])
    if check['status']!='HEALTHY':raise RuntimeError('Passive health check did not pass; no search submitted')
    authorization=supervisor.request('/api/dev/safe-recovery/checks/'+check['id']+'/authorize-stage1',{'operator_reviewed':True})
    report={'query':'home gadgets','max_results':10,'max_scrolls':0,'stage':1,'validation_id':check['id'],'authorization':authorization,'submission':'INTENT_RECORDED_NO_REPLAY'}
    # Durable intent before the single POST. A lost response is never resubmitted.
    save(report)
    job=supervisor.request('/api/dev/safe-collection',{'validation_id':check['id'],'stage':1,'queries':['home gadgets']})
    report['job']=job;save(report)
    deadline=time.monotonic()+65
    while time.monotonic()<deadline:
        with db.connect() as con:
            command=dict(con.execute('SELECT id,status,detail FROM bridge_commands WHERE id=?',(job['command_id'],)).fetchone())
        if command['status'] in ('SUCCEEDED','FAILED','EXPIRED'):break
        time.sleep(1)
    report=collect_report(report);print(json.dumps(report,indent=2),flush=True)
    return 0 if command['status']=='SUCCEEDED' else 1


if __name__=='__main__':raise SystemExit(main())
