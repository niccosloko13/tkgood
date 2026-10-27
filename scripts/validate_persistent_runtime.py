"""Fixed, bounded real validation through the Companion. No browser automation library."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from discovery_session import call, wait_command

PATH=Path('data/persistent_runtime_validation.json')


def main():
    report={'started_at':datetime.now(timezone.utc).isoformat(),'commands':[],
            'sessions':[],'no_engagement':True,'no_commit':True}
    def save():
        PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def snapshot():
        state=call('/api/status')
        if state.get('security_stop'):
            raise RuntimeError('Security stop: '+state['security_stop']['reason'])
        return state['bridge']
    def execute(body):
        snapshot()
        command=call('/api/commands',body)
        result=wait_command(command,105)
        report['commands'].append(result);save()
        print(json.dumps(result),flush=True)
        if result['status']!='SUCCEEDED':
            raise RuntimeError(result['detail'])
        time.sleep(3)  # Let the normal heartbeat publish post-command tab identity.
        report['commands'][-1]['bridge_after']=snapshot();save()
        return result
    def discover():
        execute({'type':'SEARCH','query':'home gadgets'})
        result=execute({'type':'DISCOVER_MORE_RESULTS','query':'home gadgets'})
        session=next(s for s in call('/api/discovery/sessions')['items'] if s['command_id']==result['id'])
        report['sessions'].append(session);save()
    try:
        report['bridge_before']=snapshot()
        report['library_before']=call('/api/videos/count')
        report['browser_open']=call('/api/tiktok/open',{})
        if not report['browser_open']['ok']:
            raise RuntimeError(report['browser_open']['message'])
        discover()
        video='https://www.tiktok.com/@anya.bumag/video/7665799980480826642'
        for kind in ('READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE'):
            body={'type':kind,'video_url':video}
            if kind=='READ_COMMENTS_SAMPLE':body['target_count']=30
            execute(body)
        discover()
        report['detection']=call('/api/product-candidates/detect',{})
        report['status']='SUCCEEDED'
    except Exception as error:
        report['status']='STOPPED';report['reason']=str(error)
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        report['library_after']=call('/api/videos/count')
        report['bridge_after']=call('/api/status')['bridge']
        ids={(c['bridge_after'].get('tab_id'),c['bridge_after'].get('window_id')) for c in report['commands'] if c.get('bridge_after')}
        report['same_tab_and_window']=len(ids)==1 and next(iter(ids),None)==(report.get('bridge_before',{}).get('tab_id'),report.get('bridge_before',{}).get('window_id'))
        save();print(json.dumps({'status':report['status'],'reason':report.get('reason'),'sessions':report['sessions'],'library_after':report['library_after']}),flush=True)
    return 0 if report['status']=='SUCCEEDED' else 1


if __name__=='__main__':
    raise SystemExit(main())
