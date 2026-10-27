"""Read-only evidence export. Does not contact TikTok or mutate application data."""
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app import category_intelligence as ci
from app.chrome_launcher import profile_processes

OUT=Path(__file__).resolve().parent
before=json.loads((OUT/'checkpoint.json').read_text(encoding='utf-8'))
con=sqlite3.connect('file:'+str(ROOT/'data/product_hunter.db')+'?mode=ro',uri=True)
con.row_factory=sqlite3.Row
con.execute('PRAGMA query_only=ON')
tables={}
for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    name=row[0]
    data=[dict(x) for x in con.execute('SELECT * FROM "'+name+'"')]
    tables[name]={'count':len(data),'sha256':hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()}
items=ci.library(con)
plans=[]
for _ in range(3):
    plans.append(ci.plan(con,excluded=[x['selected_query'] for x in plans]))
queue=[]
priorities=[]
weights=ci.config('discovery_intelligence')['enrichment_weights']
for item in items:
    vid=item['video_id']
    row=con.execute('SELECT thumbnail_url FROM videos WHERE id=?',(vid,)).fetchone()
    sample=con.execute('SELECT signals_json FROM comment_samples WHERE video_id=? ORDER BY id DESC LIMIT 1',(vid,)).fetchone()
    # These are queue criteria only, never new labels/classification or identity evidence.
    reasons=[]
    if not item['candidates']:reasons.append('candidate_missing')
    if row['thumbnail_url']:reasons.append('thumbnail_available')
    if item['category']['category_status']=='classified':reasons.append('category_known')
    if item['unresolved']:reasons.append('unresolved_phrase')
    if not item['caption'] or len(item['caption'].split())<3:reasons.append('caption_insufficient')
    if not sample or json.loads(sample['signals_json']).get('comments_sampled',0)<30:reasons.append('comments_insufficient')
    if {'candidate_missing','thumbnail_available'}<=set(reasons) and ({'category_known','unresolved_phrase'}&set(reasons)):
        queue.append({'video_id':vid,'platform_video_id':item['platform_video_id'],'caption':item['caption'],
                      'category':item['category'],'reasons':reasons,'source_queries':item['queries']})
    priorities.append({'video_id':vid,'priority':item['enrichment_priority'],'reasons':item['enrichment_priority_reasons'],
                       'score_matches_config':item['enrichment_priority']==sum(weights[k] for k in item['enrichment_priority_reasons'])})
status=json.load(urlopen('http://127.0.0.1:8000/api/status',timeout=8))
result={'checked_at':datetime.now(timezone.utc).isoformat(),'integrity_check':con.execute('PRAGMA integrity_check').fetchone()[0],
        'foreign_key_check':[list(x) for x in con.execute('PRAGMA foreign_key_check')],
        'profile_pids':profile_processes(),'tables':tables,
        'changed_tables':[k for k in before['tables'] if before['tables'][k]!=tables.get(k)],
        'changed_source_files':[k for k,v in before['files'].items() if not (ROOT/k).exists() or hashlib.sha256((ROOT/k).read_bytes()).hexdigest()!=v],
        'status':status,'distribution':dict(Counter(v['category']['primary_category'] or 'unclassified' for v in items)),
        'category_status':dict(Counter(v['category']['category_status'] for v in items)),
        'query_metrics':ci.query_metrics(con),'planner_offline_selections':plans,
        'enrichment_priority_audit':priorities,'visual_identification_candidates':queue,
        'new_sessions':tables['discovery_sessions']['count']-before['tables']['discovery_sessions']['count'],
        'new_videos':tables['videos']['count']-before['tables']['videos']['count']}
(OUT/'after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'visual-identification-queue.json').write_text(json.dumps({'scope':'historical persisted library only; no new discovery',
    'criteria':'candidate_missing AND thumbnail_available AND (category_known OR unresolved_phrase)',
    'count':len(queue),'items':queue},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ['integrity_check','changed_tables','distribution','category_status','new_sessions','new_videos']},indent=2))
print('Visual queue:',len(queue))
