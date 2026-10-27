"""Fixed local tasks in background. No shell, public API or arbitrary command."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
try:
    from .process_runtime import ROOT, hidden_kwargs
except ImportError:
    from process_runtime import ROOT, hidden_kwargs


def save(path, value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary,path)


def launch(task, arguments):
    if task not in ('manual-captcha-resume','selective-enrichment','resume-stage2','controlled-stage2','quarantine-stage1','visual-identity-worker','intelligence-worker','devctl','supervisor','pytest','node-tests','migrate','read-video-details','sample-comments','read-creator-profiles','detect-products','discovery-session','validate-persistent-runtime'):
        raise ValueError('Unsupported background task')
    key=uuid.uuid4().hex
    directory=ROOT/'.runtime/logs'
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/f'task-{key}.json'
    save(path,{'id':key,'task':task,'status':'STARTING','created_at':datetime.now(timezone.utc).isoformat()})
    python=ROOT/'.venv/Scripts/python.exe'
    try:
        with (directory/f'task-{key}.log').open('ab') as log:
            subprocess.Popen([str(python),str(Path(__file__).resolve()),'--worker',key,task,*arguments],
                             cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,**hidden_kwargs())
    except OSError as exc:
        save(path,{'id':key,'task':task,'status':'FAILED','exit_code':1,'error':str(exc)})
        raise
    return key


def worker(key,task,arguments):
    directory=ROOT/'.runtime/logs'
    path=directory/f'task-{key}.json'
    record=json.loads(path.read_text(encoding='utf-8'))
    record.update(status='RUNNING',pid=os.getpid())
    save(path,record)
    python=str(ROOT/'.venv/Scripts/python.exe')
    command={'manual-captcha-resume':[python,str(ROOT/'scripts/manual_captcha_resume.py')],
             'selective-enrichment':[python,str(ROOT/'scripts/selective_enrichment.py')],
             'resume-stage2':[python,str(ROOT/'scripts/resume_stage2.py')],
             'controlled-stage2':[python,str(ROOT/'scripts/controlled_stage2.py')],
             'quarantine-stage1':[python,str(ROOT/'scripts/quarantine_stage1.py'),*arguments],
             'visual-identity-worker':[python,str(ROOT/'scripts/visual_identity.py')],
             'intelligence-worker':[python,str(ROOT/'scripts/core_activation.py')],
             'devctl':[python,str(ROOT/'scripts/devctl.py'),*arguments],
             'supervisor':[python,str(ROOT/'scripts/dev_supervisor.py')],
             'validate-persistent-runtime':[python,str(ROOT/'scripts/validate_persistent_runtime.py')],
             'discovery-session':[python,str(ROOT/'scripts/discovery_session.py'),*arguments],
             'detect-products':[python,str(ROOT/'scripts/detect_products.py')],
             'migrate':[python,'-c','from app.db import init_db; init_db()'],
             'read-video-details':[python,str(ROOT/'scripts/read_video_details.py'),*arguments],
             'sample-comments':[python,str(ROOT/'scripts/sample_comments.py'),*arguments],
             'read-creator-profiles':[python,str(ROOT/'scripts/read_creator_profiles.py'),*arguments],
             'pytest':[python,'-m','pytest','-q'],
             'node-tests':['node','--test',*[str(p) for p in (ROOT/'tests').glob('*.test.cjs')]]}[task]
    try:
        result=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,**hidden_kwargs())
        record.update(status='SUCCEEDED' if result.returncode==0 else 'FAILED',exit_code=result.returncode)
    except Exception as exc:
        record.update(status='FAILED',error=str(exc),exit_code=1)
        print(str(exc),file=sys.stderr,flush=True)
    record['finished_at']=datetime.now(timezone.utc).isoformat()
    save(path,record)
    with (directory/'tasks.log').open('a',encoding='utf-8') as log:
        log.write(json.dumps(record)+'\n')
    return record['exit_code']


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker')
    parser.add_argument('task',choices=['manual-captcha-resume','selective-enrichment','resume-stage2','controlled-stage2','quarantine-stage1','visual-identity-worker','intelligence-worker','devctl','supervisor','pytest','node-tests','migrate','read-video-details','sample-comments','read-creator-profiles','detect-products','discovery-session','validate-persistent-runtime'])
    parser.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if args.worker:
        raise SystemExit(worker(args.worker,args.task,args.arguments))
    print(launch(args.task,args.arguments))
