"""DEPRECATED Stage 2 resume adapter; checkpoint policy lives in DiscoveryRunner."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dev_supervisor import Supervisor
from app import db,safe_collection as safe
import controlled_stage2 as pilot

ORIGINAL=pilot.REPORT
REPORT=ORIGINAL.with_name('resume-20261025.json')


def passive_gate():
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        try:
            with db.connect() as con:pilot.gate(con)
            return
        except RuntimeError as error:
            if str(error)!='SESSION_OR_PAGE_NOT_HEALTHY':raise
        time.sleep(1)
    raise RuntimeError('SESSION_NOT_STABLE')


def reconcile(report):
    report=pilot.reconcile(report)
    with db.connect() as con:
        diagnostic={r['command_id']:json.loads(r['diagnostics_json']) for r in con.execute('SELECT * FROM safe_search_diagnostics')}
        for metric in report['query_metrics']:metric['stability']=diagnostic.get(metric['command_id'])
        report['resume_query_metrics']=[m for m in report['query_metrics'] if m['command_id'] in report.get('commands',[])]
        report['active_runtime_seconds']=safe.runtime_used(con,report['batch']) if report.get('batch') else None
    pilot.save(report);return report


def main():
    if REPORT.exists():raise RuntimeError('Resume intent already exists; no automatic repeat')
    prior=json.loads(ORIGINAL.read_text(encoding='utf-8'))
    report={'batch_id':prior['batch_id'],'queries':prior['queries'],'queries_skipped':['home gadgets'],'baseline':{'results':prior['results'],'new_videos':prior['new_videos'],'duplicates':prior['duplicates'],'observations':prior['observations'],'trend_snapshots':prior['trend_snapshots']},'commands':[],'stage3_executed':False,'resume_intent':'EXPLICIT_ONCE'}
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    with REPORT.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    pilot.REPORT=REPORT;s=Supervisor();reason='UNCONFIRMED_OUTCOME'
    try:
        passive_gate();check=s.request('/api/dev/safe-recovery/checks',{})
        deadline=time.monotonic()+30
        while check['status']=='PENDING' and time.monotonic()<deadline:
            time.sleep(1);check=s.request('/api/dev/safe-recovery/checks/'+check['id'])
        if check['status']!='HEALTHY':raise RuntimeError('SESSION_NOT_STABLE')
        report['fresh_check_id']=check['id'];pilot.save(report)
        job=s.request('/api/dev/safe-collection/'+report['batch_id']+'/resume-stage2',{'fresh_check_id':check['id'],'operator_reviewed':True})
        if job.get('reused'):raise RuntimeError('RESUME_ALREADY_USED_NO_CONTINUATION')
        report['commands'].append(job['command_id']);pilot.save(report)
        while True:
            deadline=time.monotonic()+48
            while True:
                with db.connect() as con:
                    db.expire_commands(con)
                    command=dict(con.execute('SELECT * FROM bridge_commands WHERE id=?',(job['command_id'],)).fetchone())
                if command['status'] in ('SUCCEEDED','FAILED','EXPIRED'):break
                if time.monotonic()>=deadline:raise RuntimeError('UNCONFIRMED_OUTCOME_NO_RETRY')
                time.sleep(1)
            report=reconcile(report)
            if command['status']!='SUCCEEDED':reason=command['detail'];break
            if report['observations']!=report['trend_snapshots']:raise RuntimeError('TREND_SOURCE_COVERAGE_MISMATCH')
            if report['batch']['status']=='SUCCEEDED':reason=report['batch']['stop_reason'];break
            passive_gate()
            with db.connect() as con:
                if safe.runtime_used(con,report['batch'])>safe.MAX_RUNTIME_SECONDS-35:reason='MAX_RUNTIME';break
            report['next_query_intent']=report['queries'][report['batch']['query_index']];pilot.save(report)
            job=s.request('/api/dev/safe-collection/'+report['batch_id']+'/next',{'operator_reviewed':True})
            report['commands'].append(job['command_id']);pilot.save(report)
    except Exception as error:reason=str(error)
    finally:
        report['stop_reason']=reason
        with db.connect() as con:
            con.execute("UPDATE safe_collection_batches SET status='FAILED',stop_reason=?,completed_at=? WHERE id=? AND status IN ('READY','PAUSED')",(reason,safe.now(),report['batch_id']))
        report=reconcile(report);print(json.dumps(report,indent=2),flush=True)
    return 0 if report['batch']['status']=='SUCCEEDED' else 1


if __name__=='__main__':raise SystemExit(main())
