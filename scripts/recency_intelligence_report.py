import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import db
from app.recency_intelligence import reprocess
out=Path('artifacts/recency-intelligence');out.mkdir(parents=True,exist_ok=True)
with db.connect() as c:
 m=c.execute("SELECT id FROM viral_products_72h_missions ORDER BY created_at DESC LIMIT 1").fetchone()
 total,counts=reprocess(c,m['id'])
 confirmed=total-counts.get('UNKNOWN',0);inside=sum(counts.get(k,0) for k in ('<6h','6-12h','12-24h','24-48h','48-72h'))
 report={'mission_id':m['id'],'results_reprocessed':total,'buckets':counts,'confirmed':confirmed,'unknown':counts.get('UNKNOWN',0),'within_72h':inside,'sources':['SEARCH_CARD_VISIBLE_RELATIVE_TIME only when an explicit standalone relative-age marker was persisted'],'limitations':['No video IDs were decoded into timestamps.','No video was opened.','Persisted mission cards did not expose a proven createTime/publishTime field.']}
 out.joinpath('REPORT.md').write_text('# Recency Intelligence\n\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n\n## Top Picks\n\nNone promoted without confirmed <=72h publication evidence.\n',encoding='utf-8')
