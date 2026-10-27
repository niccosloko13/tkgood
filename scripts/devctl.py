"""Local CLI. All administration is opt-in, authenticated and loopback-only."""
import argparse
from datetime import datetime, timezone
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from process_runtime import logged

from dev_supervisor import Supervisor, DevError, build_extension


def wait_until(check, timeout, description):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        result=check()
        if result:
            return result
        time.sleep(.4)
    raise DevError(f'Timeout after {timeout}s: {description}')


def bridge_ready(status, build, since):
    bridge=status.get('bridge',{})
    try:
        fresh=datetime.fromisoformat(bridge['last_seen']) >= since
    except (KeyError,TypeError,ValueError):
        return False
    return bool(fresh and bridge.get('connected') and bridge.get('tiktok_open') and
                bridge.get('build_id') == build and bridge.get('page_signals',{}).get('content_script_connected'))


def dev_command(supervisor, kind, build, timeout):
    supervisor.drain()
    since=datetime.now(timezone.utc)
    command=supervisor.request('/api/dev/commands',{'type':kind,'expected_build':build})
    print(f'Command {command["id"]}: {kind}',flush=True)
    def finished():
        state=next((job for job in supervisor.request('/api/dev/status')['jobs'] if job['id']==command['id']),None)
        if state and state['status'] in ('FAILED','EXPIRED'):
            raise DevError(f'{kind} {state["status"]}: {state["detail"]}')
        return state if state and state['status']=='SUCCEEDED' else None
    result=wait_until(finished,timeout,f'{kind} completion (extension may need initial bootstrap)')
    print(f'Companion build {result["build_id"]}; refreshed TikTok tabs: {result["refreshed_tabs"]}',flush=True)
    if result['refreshed_tabs'] == 0:
        status=supervisor.request('/api/status')
        bridge=status.get('bridge',{})
        if (kind=='DEV_RELOAD_EXTENSION' and (status.get('security_stop') or {}).get('reason') and
                bridge.get('connected') and bridge.get('build_id')==build and
                datetime.fromisoformat(bridge['last_seen'])>=since):
            print('Companion connected; security stop retained; no TikTok navigation.',flush=True)
            return result
        raise DevError('Companion completed but no existing TikTok tab was found')
    wait_until(lambda: bridge_ready(supervisor.request('/api/status'),build,since),timeout,'fresh TikTok content-script heartbeat')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['status','restart-backend','reload-extension','refresh-tiktok','reload-all','validate-home','clear-reviewed-stop'])
    parser.add_argument('--validation-id')
    parser.add_argument('--timeout',type=float,default=65)
    args=parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    supervisor=Supervisor()
    stage='initialization'
    acquired=False
    control=supervisor.lock()
    try:
        control.__enter__()
        acquired=True
        if acquired:
            if args.command=='status':
                health=supervisor.healthy()
                bridge=(health or {}).get('bridge',{})
                print(json.dumps({'backend':'healthy' if health else 'offline','supervisor_owned':bool(supervisor.record()),
                    'extension':bridge.get('extension_connected',False),'tiktok_tab':bridge.get('tiktok_open',False),
                    'bridge':bridge.get('connected',False),'companion_version':bridge.get('companion_version') or bridge.get('extension_version'),
                    'build_id':bridge.get('build_id'),'last_heartbeat':bridge.get('last_seen')},indent=2))
                return 0 if health else 1
            supervisor.provision()
            build=build_extension()
            if args.command=='clear-reviewed-stop':
                if not args.validation_id:
                    raise DevError('--validation-id is required; nothing cleared')
                print(json.dumps(supervisor.request('/api/dev/recovery/'+args.validation_id+'/clear-reviewed-stop',{})))
                return 0
            if args.command in ('restart-backend','reload-all'):
                stage='[1/6] Restarting Product Hunter backend'
                print(stage+'...',flush=True)
                supervisor.restart()
                print('[2/6] Backend healthy.',flush=True)
            if args.command in ('reload-extension','reload-all','refresh-tiktok','validate-home'):
                stage='[3/6] Requesting Companion reload' if args.command!='refresh-tiktok' else 'Refreshing TikTok tabs'
                print(stage+'...',flush=True)
                bridge=supervisor.request('/api/status').get('bridge',{})
                if not bridge.get('build_id') or not bridge.get('connected'):
                    from bootstrap_companion import bootstrap
                    supervisor.drain()
                    print('Bootstrap: reconnecting the Companion through its local page in the existing dedicated Chrome only...',flush=True)
                    bootstrap()
                    wait_until(lambda: (lambda b: b.get('connected') and b.get('build_id')==build)(supervisor.request('/api/status').get('bridge',{})),
                               args.timeout,'initial Companion DEV build heartbeat')
                kind={'refresh-tiktok':'DEV_REFRESH_TIKTOK','validate-home':'DEV_VALIDATE_TIKTOK_HOME'}.get(args.command,'DEV_RELOAD_EXTENSION')
                dev_command(supervisor,kind,build,args.timeout)
                print('[4/6] Companion running expected build.\n[5/6] TikTok tabs refreshed.\n[6/6] Bridge connected.',flush=True)
            print('READY',flush=True)
            return 0
    except (DevError,OSError,ValueError,KeyError) as exc:
        print(f'ERROR at {stage}: {exc}',file=sys.stderr,flush=True)
        return 1
    finally:
        if acquired and args.command!='status':
            try:
                supervisor.request('/api/dev/resume',{})
            except (OSError,ValueError):
                pass
        if acquired:
            control.__exit__(None,None,None)


if __name__=='__main__':
    with logged('devctl.log'):
        raise SystemExit(main())
