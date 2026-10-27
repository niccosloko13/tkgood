"""Read up to eight already-captured videos, sequentially through the Companion.

No browser automation library, click endpoint, account action or TikTok API.
"""
import argparse
import json
import time
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture-id', required=True)
    parser.add_argument('--limit', type=int, default=8, choices=range(1, 9))
    parser.add_argument('--start-position', type=int, default=1, choices=range(1,101))
    args = parser.parse_args()
    base = 'http://127.0.0.1:8000'

    def request(path, payload=None):
        req = Request(base+path, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={'Content-Type':'application/json'})
        with urlopen(req, timeout=6) as response:
            return json.load(response)

    items = request('/api/videos/recent')['items']
    videos = sorted((v for v in items if v['capture_id']==args.capture_id and
                     (v['search_position'] or 0)>=args.start_position), key=lambda v:v['search_position'] or 0)[:args.limit]
    if not videos:
        raise SystemExit('No recent library videos match this capture; nothing opened')
    results=[]
    for index, video in enumerate(videos, 1):
        command=request('/api/commands', {'type':'READ_VIDEO_DETAIL','video_url':video['video_url']})
        print(json.dumps({'step':index,'of':len(videos),'video_id':video['video_id'],'command_id':command['id'],'status':command['status']}),flush=True)
        deadline=time.monotonic()+48
        while time.monotonic()<deadline:
            states=request('/api/commands')['items']
            state=next((item for item in states if item['id']==command['id']), None)
            if state and state['status'] in ('SUCCEEDED','FAILED','EXPIRED'):
                results.append({'video_id':video['video_id'],'command_id':state['id'],'status':state['status'],'detail':state['detail']})
                print(json.dumps(results[-1]),flush=True)
                if state['status'] != 'SUCCEEDED':
                    raise SystemExit('Read failed; stopping before opening another video')
                break
            time.sleep(1)
        else:
            raise SystemExit('Command outcome not confirmed; stopping instead of opening another video')
    print(json.dumps({'completed':len(results),'succeeded':sum(r['status']=='SUCCEEDED' for r in results),'results':results}),flush=True)


if __name__=='__main__':
    main()
