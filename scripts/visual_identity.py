"""Bounded visual work on real persisted assets using the existing queue."""
import os
os.environ['HF_HUB_OFFLINE']='1'
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import init_db,connect
from app import visual_identification as vi,intelligence_jobs as jobs,intelligence_core as core
from app.visual_providers import config
from app.intelligence_embeddings import provider


def main():
    from filelock import FileLock,Timeout
    init_db();deadline=time.monotonic()+300;results=[]
    try:
        with FileLock('data/intelligence/activation-worker.lock',timeout=120),connect() as con:
            priorities={r['video_id']:r['priority'] for r in vi.needs_visual(con)}
            ids=[r[0] for r in con.execute('SELECT id FROM videos ORDER BY id') if vi.image_source(con,r[0])['status']=='available']
            ids.sort(key=lambda vid:(priorities.get(vid,'D'),vid))
            for vid in ids[:config()['max_items']]:
                if time.monotonic()>=deadline:break
                context=vi.persisted_visual_context(con,vid)
                jid=jobs.enqueue(con,'visual_identity',vid,{'image_sha256':context['image']['sha256'],'context_hash':core.fingerprint(context),'config':config()})
                con.commit()
                while time.monotonic()<deadline:
                    job=jobs.claim(con,job_id=jid);con.commit()
                    if not job:break
                    started=time.monotonic()
                    try:
                        result=vi.run_visual_identity(con,vid);results.append(result)
                        if result['status']=='deferred':
                            jobs.defer(con,job,result.get('error','RESOURCE_DEFER'));con.commit()
                            delay=core.settings()['resources']['cooldown_seconds']
                            if time.monotonic()+delay>=deadline:break
                            time.sleep(delay);continue
                        if result['status']=='blocked':jobs.finish(con,job,failure='SECURITY_BLOCK',reason=result['reason'])
                        elif result['status']=='unavailable':jobs.finish(con,job,failure='INSUFFICIENT_DATA',reason=result['reason'])
                        else:jobs.finish(con,job,status=result.get('decision',{}).get('status','unresolved').lower(),reason=result.get('decision',{}).get('reason_code'),processing_ms=(time.monotonic()-started)*1000)
                        con.commit()
                    except Exception as exc:
                        jobs.finish(con,job,failure='PERMANENT',reason='VISUAL_PIPELINE_ERROR',error=type(exc).__name__);con.commit();raise
                    break
                if results and results[-1]['status']=='blocked':break
            directory=Path('artifacts/visual-identity-completion');directory.mkdir(parents=True,exist_ok=True)
            (directory/'worker.json').write_text(json.dumps({'results':results,'visual_summary':vi.visual_summary(con),'counts':core.overview(con)['counts']},ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'assets':len(ids),'processed_jobs':len(results)}))
    except Timeout:print('DEFERRED_WORKER_OWNERSHIP')
    finally:provider.unload()


if __name__=='__main__':main()
