"""Request one bounded read-only sample via the existing normal Chrome bridge."""
import argparse
import json
import time
from urllib.request import Request,urlopen


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('video_url')
    parser.add_argument('--target',type=int,default=30,choices=range(1,101))
    args=parser.parse_args()
    def call(path,payload=None):
        request=Request('http://127.0.0.1:8000'+path,data=json.dumps(payload).encode() if payload is not None else None,
                        headers={'Content-Type':'application/json'})
        with urlopen(request,timeout=6) as response: return json.load(response)
    command=call('/api/commands',{'type':'READ_COMMENTS_SAMPLE','video_url':args.video_url,'target_count':args.target})
    print(json.dumps(command),flush=True)
    deadline=time.monotonic()+100
    while time.monotonic()<deadline:
        state=next((item for item in call('/api/commands')['items'] if item['id']==command['id']),None)
        if state and state['status'] in ('SUCCEEDED','FAILED','EXPIRED'):
            print(json.dumps(state),flush=True)
            if state['status']!='SUCCEEDED': raise SystemExit('Sampling failed; no next video opened')
            video_id=command['query'].rsplit('/',1)[1]
            result=call(f'/api/videos/{video_id}/comments')['items'][0]
            print(json.dumps({key:value for key,value in result.items() if key!='comments'},ensure_ascii=True),flush=True)
            return
        time.sleep(1)
    raise SystemExit('Sampling outcome not confirmed; stopped')


if __name__=='__main__': main()
