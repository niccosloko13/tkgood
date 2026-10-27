"""Bounded local pilot then library activation. All network access is denied.

Resume uses persisted embeddings/decisions and the existing job queue. Waiting
for resource admission does not turn into a permanent inference failure.
"""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
import argparse
import json
from pathlib import Path
import socket
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import connect,init_db
from app import intelligence_core as core
from app.intelligence_embeddings import provider,ResourceGovernor,ResourceBusy
from app.intelligence_index import ProductIndex


def no_network(*args,**kwargs):raise RuntimeError('OFFLINE_WORKER_NETWORK_FORBIDDEN')


def main(runtime=180,run_all=True):
    socket.socket.connect=no_network
    init_db()
    directory=Path('artifacts/core-activation');directory.mkdir(parents=True,exist_ok=True)
    output={'status':'running','network':'denied','resource_samples':[]}
    def save():
        temp=directory/'pilot.tmp';temp.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,directory/'pilot.json')
    with connect() as con:
        observations=[core.observation(con,r[0]) for r in con.execute('SELECT id FROM videos ORDER BY id').fetchall()]
        images=[v for v in observations if v['image']['status']=='available']
        strong=[v for v in observations if core.evidence_for(v)['text_identity_specific'] and core.evidence_for(v)['text_caption_supported'] and v['video_id'] not in (1,3)]
        ids=list(dict.fromkeys([1,3]+[v['video_id'] for v in images[:3]]+[v['video_id'] for v in strong[:3]]))
        output['pilot_ids']=ids;output['additional_image_items_available']=len([v for v in images if v['video_id'] not in (1,3)])
        output['text_pilot']=[core.identify(con,vid) for vid in ids];con.commit();save()
        deadline=time.monotonic()+runtime
        if not images:output['status']='blocked_no_local_image';save();return output
        item=images[0];vid=item['video_id'];raw=core.visual.image_bytes(con,vid)[0]
        while True:
            state=ResourceGovernor().state();output['resource_samples'].append(state);save()
            try:
                vector=provider.embed(con,'image',raw);first=dict(provider.last_inference)
                again=provider.embed(con,'image',raw);second=dict(provider.last_inference)
                assert vector==again and second['cache_status']=='hit'
                output['openclip_smoke']={'video_id':vid,'asset_id':item['image']['asset_id'],'first':first,'second':second,'probe':provider.runtime_probe}
                con.commit();save()
                metadata=core.rebuild_index(con);con.commit();output['index']=metadata
                output['retrieval']=ProductIndex().search(vector,provider.version)
                output['visual_pilot']=core.identify(con,vid,with_embeddings=True);con.commit();save()
                break
            except ResourceBusy as exc:
                output['status']='waiting';output['wait_reason']=str(exc);save()
                if time.monotonic()+core.settings()['resources']['cooldown_seconds']>=deadline:
                    output['status']='deferred';save();provider.unload();return output
                con.commit()
                time.sleep(core.settings()['resources']['cooldown_seconds'])
        if run_all:
            core.enqueue_library(con);output['library_processed']=core.process(con)
        output['overview']=core.overview(con)
        # Labels are opened only after the production pilot/library have finished.
        from app.intelligence_evaluation import evaluate
        output['gold_evaluation']=evaluate(con)
        output['status']='completed';save();provider.unload()
        output['model_unloaded']=provider.model is None;save()
        print(json.dumps({'status':output['status'],'pilot_ids':ids,'counts':output['overview']['counts'],'vectors':metadata['vectors']}),flush=True)
        return output


if __name__=='__main__':
    from filelock import FileLock,Timeout
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=int,default=180);parser.add_argument('--pilot-only',action='store_true')
    args=parser.parse_args()
    Path('data/intelligence').mkdir(parents=True,exist_ok=True)
    try:
        with FileLock('data/intelligence/activation-worker.lock',timeout=0):main(min(max(args.runtime,1),300),not args.pilot_only)
    except Timeout:print('ALREADY_RUNNING',flush=True)
