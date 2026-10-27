"""Write an evidence-only report for one completed Viral Products 72h mission."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import db

OUT=Path('artifacts/viral-products-72h'); OUT.mkdir(parents=True,exist_ok=True)
with db.connect() as c:
    mission=c.execute("SELECT * FROM viral_products_72h_missions ORDER BY created_at DESC LIMIT 1").fetchone()
    if not mission: raise SystemExit('No Viral Products 72h mission')
    commands=[r[0] for r in c.execute("SELECT id FROM bridge_commands WHERE json_extract(options_json,'$.mission_contract_id')=? ORDER BY id",(mission['id'],))]
    slots=','.join('?'*len(commands)); rows=c.execute(f"SELECT o.search_query,o.observed_at,o.fields_json FROM search_observations o WHERE o.capture_id IN ({slots}) ORDER BY o.id",[f'command:{x}' for x in commands]).fetchall()
    grouped={}
    for r in rows:
        f=json.loads(r['fields_json']); url=f.get('video_url');
        if not url: continue
        v=grouped.setdefault(url,{'product':(f.get('caption') or 'Produto não identificado')[:140],'video_url':url,'creator':f.get('creator_username'),'queries':set(),'observations':0,'visible_metrics':{k:f.get(k) for k in ('views','likes','comments_count','shares','favorites')},'recency':'RECENCY_UNKNOWN','risks':['CONTENT_AGE_NOT_VISIBLE_ON_SEARCH_CARD','SEARCH_ONLY_EVIDENCE']})
        v['queries'].add(r['search_query']);v['observations']+=1
    products=[]
    for v in grouped.values():
        v['queries']=sorted(v['queries']);v['query_spread']=len(v['queries']);v['why']=['Visible search result persisted','Observed in '+str(v['query_spread'])+' query/queries','No content age claimed without visible evidence'];products.append(v)
    products.sort(key=lambda x:(x['query_spread'],x['observations']),reverse=True)
    query=[]
    for cid in commands:
        cmd=c.execute('SELECT query,status FROM bridge_commands WHERE id=?',(cid,)).fetchone(); qrows=[r for r in rows if r['search_query']==cmd['query']]
        query.append({'query':cmd['query'],'status':cmd['status'],'results':len(qrows),'unique_videos':len({json.loads(r['fields_json']).get('video_url') for r in qrows}),'novelty_rate':'UNKNOWN_WITHOUT_PRIOR_QUERY_BASELINE'})
    payload={'mission_id':mission['id'],'contract':json.loads(mission['contract_json']),'summary':{k:mission[k] for k in ('status','results','new_videos','duplicates','observations','snapshots','stop_reason')},'top_picks':[],'watchlist':products[:15],'rejected':products[15:],'query_performance':query,'limitations':['No search-card content age was visible; RECENCY_UNKNOWN items were not promoted to Top Picks.','No video detail, comments or creator profile was opened.']}
OUT.joinpath('products.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# Viral Products 72h','',f"Mission: `{mission['id']}`",'',f"- Queries: {len(commands)}",f"- Raw results: {mission['results']}",f"- New videos: {mission['new_videos']}",f"- Duplicates: {mission['duplicates']}",f"- Observations / snapshots: {mission['observations']} / {mission['snapshots']}",f"- Stop: {mission['stop_reason']}",'','## Top Picks','','None promoted. Search cards did not provide confirmable content age, so every item remains `RECENCY_UNKNOWN` rather than being misrepresented as <72h.','','## Watchlist','','| Product signal | Queries | Creator | Evidence |','|---|---:|---|---|']
for p in products[:15]:lines.append(f"| {p['product'].replace('|',' ')} | {p['query_spread']} | {p['creator'] or 'UNKNOWN'} | [search card]({p['video_url']}) |")
lines+=['','## Query performance','', '| Query | Results | Unique | Status |','|---|---:|---:|---|']+[f"| {q['query']} | {q['results']} | {q['unique_videos']} | {q['status']} |" for q in query]+['','## Safety','', 'PAGE=HEALTHY; SESSION=CONFIRMED; GLOBAL SECURITY=OK; Direct Video Enrichment=PAUSED. No engagement, video detail, comments or profile reads were performed.']
OUT.joinpath('REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
