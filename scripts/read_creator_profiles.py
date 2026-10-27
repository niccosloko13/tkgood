"""Read at most five existing creators sequentially through the normal Companion."""
import argparse
import json
import time
from urllib.request import Request, urlopen


def call(path, body=None):
    req=Request('http://127.0.0.1:8000'+path,data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=8) as response:
        return json.load(response)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--limit',type=int,choices=range(1,6),default=1)
    parser.add_argument('--video-url')
    args=parser.parse_args()
    creators=call('/api/creators')['items']
    selected=[]
    for creator in creators:
        videos=creator['related_videos']
        if args.video_url:
            videos=[v for v in videos if v['video_url']==args.video_url]
        if videos:
            selected.append((creator,videos[0]))
    selected=selected[:args.limit]
    if not selected:
        raise SystemExit('No observed creator linked to the requested library video')
    for creator,video in selected:
        command=call('/api/commands',{'type':'READ_CREATOR_PROFILE','video_url':video['video_url']})
        print(json.dumps({'creator':creator['username'],'command_id':command['id'],'status':command['status']}),flush=True)
        deadline=time.monotonic()+48
        while time.monotonic()<deadline:
            state=next((item for item in call('/api/commands')['items'] if item['id']==command['id']),None)
            if state and state['status'] in ('SUCCEEDED','FAILED','EXPIRED'):
                print(json.dumps(state),flush=True)
                if state['status']!='SUCCEEDED':
                    raise SystemExit('Read failed; stopped before opening another creator')
                updated=call('/api/creators/'+str(creator['creator_id']))['items'][0]
                print(json.dumps({'username':updated['username'],'signals':updated['signals'],'observation':updated['latest_observed_at']}),flush=True)
                break
            time.sleep(1)
        else:
            raise SystemExit('Outcome not confirmed; stopped before next creator')


if __name__=='__main__':
    main()
