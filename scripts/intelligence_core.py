"""Explicit offline bounded run. No browser runtime or remote providers."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import connect,init_db
from app import intelligence_core as core


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--embeddings',action='store_true')
    p.add_argument('--rebuild-index',action='store_true')
    p.add_argument('--evaluate',action='store_true')
    args=p.parse_args()
    init_db()
    with connect() as con:
        core.migrate(con)
        ids=core.enqueue_library(con,args.embeddings)
        results=core.process(con,with_embeddings=args.embeddings)
        if args.rebuild_index:
            from app import intelligence_jobs as jobs
            jobs.enqueue(con,'index_rebuild','approved-products',{'version':core.settings()['version'],'entities':[r[0] for r in con.execute('SELECT id FROM intelligence_entities ORDER BY id')]})
            results.extend(core.process(con,limit=1,with_embeddings=True))
        output={'job_ids':ids,'processed':results,'overview':core.overview(con)}
        if args.evaluate:
            from app.intelligence_evaluation import evaluate
            output['evaluation']=evaluate(con)
        directory=Path('artifacts/intelligence-core-consolidation');directory.mkdir(parents=True,exist_ok=True)
        (directory/'results.json').write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps({'processed':len(results),'counts':output['overview']['counts'],'model_loaded':output['overview']['model_loaded']}))


if __name__=='__main__':main()
