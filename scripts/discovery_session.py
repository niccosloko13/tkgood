"""One user-selected bounded query; no branching, stealth or TikTok API."""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request,urlopen


def call(path,body=None):
    req=Request('http://127.0.0.1:8000'+path,data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=8) as response:return json.load(response)


def wait_command(command,seconds=100):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        state=next((c for c in call('/api/commands')['items'] if c['id']==command['id']),None)
        if state and state['status'] in ('SUCCEEDED','FAILED','EXPIRED'):
            return state
        time.sleep(2)
    raise RuntimeError('Command outcome not confirmed; no further browser action attempted')


def save(name,record):
    Path('data/'+name).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=True),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--query',default='home gadgets')
    parser.add_argument('--enrich-session',type=int)
    parser.add_argument('--limit',type=int,default=3,choices=range(1,11))
    args=parser.parse_args()
    if args.enrich_session:
        return enrich(args.enrich_session,args.limit)
    search=call('/api/commands',{'type':'SEARCH','query':args.query})
    outcome=wait_command(search)
    if outcome['status']!='SUCCEEDED':
        save('discovery_validation.json',{'stage':'search','outcome':outcome,'discovery_executed':False});return
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        bridge=call('/api/status')['bridge']
        from urllib.parse import urlsplit,parse_qs
        url=urlsplit(bridge.get('url',''))
        if url.path.rstrip('/')=='/search' and parse_qs(url.query).get('q',[''])[0]==args.query and bridge.get('page_signals',{}).get('page_ready_state')=='complete':
            break
        # Some legacy heartbeats expose readiness only via content-script presence.
        if url.path.rstrip('/')=='/search' and parse_qs(url.query).get('q',[''])[0]==args.query and bridge.get('page_signals',{}).get('content_script_connected'):
            time.sleep(3);break
        time.sleep(2)
    else:raise RuntimeError('Search readiness not confirmed; discovery not submitted')
    command=call('/api/commands',{'type':'DISCOVER_MORE_RESULTS','query':args.query})
    outcome=wait_command(command,105)
    session=next(s for s in call('/api/discovery/sessions')['items'] if s['command_id']==command['id'])
    save('discovery_validation.json',{'stage':'discovery','outcome':outcome,'session':session,
         'visible_start':session['visible_start'],'scrolls':session['scroll_count'],'unique_seen':session['unique_videos'],
         'new_inserted':session['new_videos'],'duplicates':session['duplicates'],'stop_reason':session['stop_reason']})


def enrich(session_id,limit):
    queue=call(f'/api/discovery/enrichment-queue?session_id={session_id}')['items'][:limit]
    results=[];stopped=False
    for video in queue:
        result={'video_url':video['canonical_url'],'commands':[]};results.append(result)
        for kind in ('READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE'):
            body={'type':kind,'video_url':video['canonical_url']}
            if kind=='READ_COMMENTS_SAMPLE':body['target_count']=30
            try:
                command=call('/api/commands',body);outcome=wait_command(command)
            except Exception as error:
                result['error']=str(error);stopped=True;break
            result['commands'].append(outcome)
            print(json.dumps({'video_url':result['video_url'],'command':outcome},ensure_ascii=True),flush=True)
            if outcome['status']!='SUCCEEDED':stopped=True;break
        if stopped:break
    detection=call('/api/product-candidates/detect',{})
    candidates=call('/api/product-candidates')['items']
    relationships=call('/api/product-candidates/relationships')['items']
    unresolved=call('/api/product-candidates/unresolved-phrases')['items']
    save('discovery_enrichment_validation.json',{'session_id':session_id,'sample_limit':limit,'selected':len(queue),
        'attempted':len(results),'stopped_early':stopped,'results':results,'detection':detection,
        'candidates':len(candidates),'cross_video_candidates':sum(c.get('independent_video_count',0)>1 for c in candidates),
        'cross_creator_candidates':sum(c.get('independent_creator_count',0)>1 for c in candidates),
        'corroborated':sum(c['status']=='corroborated' for c in candidates),
        'related_candidate_pairs':len({(r['candidate_a'],r['candidate_b']) for r in relationships}),
        'unresolved_phrases':len(unresolved)})


if __name__=='__main__':main()
