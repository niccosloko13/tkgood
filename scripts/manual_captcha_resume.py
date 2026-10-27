"""One next-HIGH candidate after explicit manual CAPTCHA recovery. No retry."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dev_supervisor import Supervisor
from app import db,safe_collection as safe,selective_enrichment as selective,target_safety

REPORT=Path(__file__).resolve().parents[1]/'artifacts/selective-enrichment/manual-captcha-resume-v1.json'


def save(report):
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    temporary=REPORT.with_suffix('.tmp');temporary.write_text(json.dumps(report,indent=2),encoding='utf-8');temporary.replace(REPORT)


def main():
    if REPORT.exists():raise RuntimeError('Single-candidate recovery intent already exists; no automatic repeat')
    report={'intent':'EXPLICIT_MANUAL_CAPTCHA_RECOVERY_ONE_CANDIDATE','parent_run_id':1,'max_candidates':1}
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    with REPORT.open('x',encoding='utf-8') as stream:json.dump(report,stream)
    result=None
    try:
        with db.connect() as c:report['temporary_quarantine']=target_safety.quarantine_challenge_context(c,1)
        save(report);s=Supervisor()
        check=s.request('/api/dev/safe-recovery/checks',{})
        deadline=time.monotonic()+30
        while check['status']=='PENDING' and time.monotonic()<deadline:
            time.sleep(1);check=s.request('/api/dev/safe-recovery/checks/'+check['id'])
        report['passive_check']=check;save(report)
        if check['status']!='HEALTHY':raise RuntimeError('PASSIVE_CHECK_NOT_HEALTHY_GLOBAL_STOP_RETAINED')
        report['release']=s.request('/api/dev/manual-captcha/release',{'check_id':check['id'],'parent_run_id':1,'operator_reviewed':True});save(report)
        child=s.request('/api/dev/manual-captcha/'+check['id']+'/next-high',{'operator_reviewed':True});report['child']=child;save(report)
        if child.get('reused'):raise RuntimeError('RECOVERY_ALREADY_USED_NO_REPEAT')
        result=selective.run(child['id']);report['result']=result
    except Exception as error:report['error']=str(error)
    finally:
        with db.connect() as c:
            b=safe.state(c,'tiktok_bridge');report['final_page']=b.get('current_page_status');report['session']=b.get('tiktok_session_status');report['global_security']=safe.state(c,'browser_security_stop')
        save(report);print(json.dumps(report,indent=2),flush=True)
    return 0 if result and result['run']['status']=='COMPLETED' else 1


if __name__=='__main__':raise SystemExit(main())
