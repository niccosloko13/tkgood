"""Explicit local operations. Check never navigates; no combined check+release."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dev_supervisor import Supervisor


def main():
    p=argparse.ArgumentParser()
    p.add_argument('operation',choices=['check','release','stage1','stage2','next','status'])
    p.add_argument('--validation-id');p.add_argument('--batch-id')
    p.add_argument('--query',action='append',default=[])
    p.add_argument('--operator-reviewed',action='store_true')
    args=p.parse_args();s=Supervisor()
    if args.operation=='status':result=s.request('/api/collection-health')
    elif args.operation=='check':
        result=s.request('/api/dev/safe-recovery/checks',{})
        deadline=time.monotonic()+30
        while result['status']=='PENDING' and time.monotonic()<deadline:
            time.sleep(1);result=s.request('/api/dev/safe-recovery/checks/'+result['id'])
    elif args.operation=='release':
        if not args.operator_reviewed or not args.validation_id:p.error('Explicit --operator-reviewed and --validation-id required')
        result=s.request('/api/dev/safe-recovery/checks/'+args.validation_id+'/release',{'operator_reviewed':True})
    elif args.operation=='next':
        if not args.operator_reviewed or not args.batch_id:p.error('Explicit --operator-reviewed and --batch-id required')
        result=s.request('/api/dev/safe-collection/'+args.batch_id+'/next',{'operator_reviewed':True})
    else:
        if not args.validation_id:p.error('--validation-id required')
        result=s.request('/api/dev/safe-collection',{'validation_id':args.validation_id,'stage':1 if args.operation=='stage1' else 2,'queries':args.query})
    print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
