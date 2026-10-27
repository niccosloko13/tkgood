"""Read-only report data and checkpoint verification for the visual pilot."""
from pathlib import Path
import json
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import visual_identification as vi,intelligence_core as core
from app.intelligence_evaluation import evaluate_visual


def main():
    directory=Path('artifacts/visual-identity-completion')
    before=sqlite3.connect(str(directory/'checkpoint.db'));before.row_factory=sqlite3.Row
    after=sqlite3.connect('file:data/product_hunter.db?mode=ro',uri=True);after.row_factory=sqlite3.Row
    after.execute('PRAGMA query_only=ON');preservation={}
    for (table,) in before.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        cols=','.join('"'+r['name']+'"' for r in before.execute('PRAGMA table_info("'+table+'")'))
        serialize=lambda rows:sorted(json.dumps(list(r),ensure_ascii=False,default=str) for r in rows)
        old=serialize(before.execute('SELECT '+cols+' FROM "'+table+'"'));new=serialize(after.execute('SELECT '+cols+' FROM "'+table+'"'))
        preservation[table]={'identical':old==new,'original_rows_preserved':set(old)<=set(new),'before':len(old),'after':len(new)}
    mutable={'events','system_state','visual_product_evidence','visual_product_search_evidence','visual_pilots'}
    protected=[t for t in preservation if not t.startswith('intelligence_') and t not in mutable]
    assert all(preservation[t]['identical'] for t in protected)
    security={}
    for key in ('browser_security_stop','browser_security_history'):
        a=before.execute('SELECT * FROM system_state WHERE key=?',(key,)).fetchone();b=after.execute('SELECT * FROM system_state WHERE key=?',(key,)).fetchone()
        security[key]={'unchanged':list(a or [])==list(b or []),'record':dict(b) if b else None}
    assert all(v['unchanged'] for v in security.values())
    assert preservation['intelligence_decisions']['original_rows_preserved']
    assert preservation['events']['original_rows_preserved']
    overview=core.overview(after);details=[]
    for row in after.execute('SELECT id FROM videos'):
        image=vi.image_source(after,row[0])
        if image['status']!='available':continue
        proposals=vi.proposals(after,row[0],active_only=True)
        details.append({'video_id':row[0],'image':image,'context':vi.persisted_visual_context(after,row[0]),'active_proposals':proposals})
    old_states={r['video_id']:r['status'] for r in before.execute('SELECT * FROM intelligence_decisions WHERE id IN (SELECT max(id) FROM intelligence_decisions GROUP BY video_id)')}
    current_states={r['video_id']:r['status'] for r in core.latest(after)}
    eligible=[vid for vid,state in old_states.items() if state=='UNRESOLVED'];recovered=sum(current_states.get(vid) in ('AUTO','REVIEW') for vid in eligible)
    evaluation=evaluate_visual(after);evaluation['unresolved_recovery']={'count':recovered,'denominator':len(eligible),'rate':recovered/len(eligible) if eligible else None}
    result={'overview':overview,'local_visual_details':details,'evaluation':evaluation,'preservation':preservation,'security':security,
            'protected_tables_identical':len(protected),'stored_hypotheses':after.execute('SELECT count(*) FROM visual_product_evidence').fetchone()[0],
            'embedding_inventory':[dict(r) for r in after.execute('SELECT kind,count(*) count FROM intelligence_embeddings GROUP BY kind')],
            'new_entities':after.execute('SELECT count(*) FROM intelligence_entities').fetchone()[0],
            'new_human_reviews':after.execute('SELECT count(*) FROM intelligence_reviews').fetchone()[0]}
    (directory/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'counts':overview['counts'],'visual_summary':{k:v for k,v in overview['visual_identity'].items() if k not in ('queue','hypotheses')},'evaluation':result['evaluation'],'security_unchanged':True},ensure_ascii=True))


if __name__=='__main__':main()
