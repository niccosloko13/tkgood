"""Read-only activation export; verifies original data against its checkpoint."""
from pathlib import Path
import hashlib
import json
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import intelligence_core as core
from app.intelligence_evaluation import evaluate


def encoded(row):return json.dumps(list(row),ensure_ascii=False,default=str)


def main():
    directory=Path('artifacts/core-activation')
    before=sqlite3.connect(str(directory/'checkpoint.db'));before.row_factory=sqlite3.Row
    after=sqlite3.connect('file:data/product_hunter.db?mode=ro',uri=True);after.row_factory=sqlite3.Row
    after.execute('PRAGMA query_only=ON')
    verification={}
    for (table,) in before.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        columns=','.join('"'+r['name']+'"' for r in before.execute('PRAGMA table_info("'+table+'")'))
        old=[encoded(r) for r in before.execute('SELECT '+columns+' FROM "'+table+'"')]
        current=[encoded(r) for r in after.execute('SELECT '+columns+' FROM "'+table+'"')]
        verification[table]={'before_count':len(old),'after_count':len(current),'identical':sorted(old)==sorted(current),'all_original_rows_preserved':set(old)<=set(current)}
    security={}
    for key in ('browser_security_stop','browser_security_history'):
        a=before.execute('SELECT * FROM system_state WHERE key=?',(key,)).fetchone()
        b=after.execute('SELECT * FROM system_state WHERE key=?',(key,)).fetchone()
        security[key]={'unchanged':list(a or [])==list(b or []),'record':dict(b) if b else None}
    overview=core.overview(after)
    metrics={'overview':overview,'gold_evaluation':evaluate(after),'security':security,'preservation':verification,
             'embedding_inventory':[dict(r) for r in after.execute('SELECT kind,count(*) AS count FROM intelligence_embeddings GROUP BY kind')],
             'entities':after.execute('SELECT count(*) FROM intelligence_entities').fetchone()[0],
             'entity_links':after.execute('SELECT count(*) FROM intelligence_entity_observations').fetchone()[0],
             'category_distribution':[dict(r) for r in after.execute('SELECT primary_category,category_status,count(*) count FROM video_category_classifications WHERE id IN (SELECT max(id) FROM video_category_classifications GROUP BY video_id) GROUP BY primary_category,category_status')],
             'current_reasons':[dict(r) for r in after.execute('SELECT reason_code,count(*) count FROM intelligence_decisions WHERE id IN (SELECT max(id) FROM intelligence_decisions GROUP BY video_id) GROUP BY reason_code')]}
    protected=[t for t in verification if not t.startswith('intelligence_') and t not in ('events','system_state')]
    assert all(verification[t]['identical'] for t in protected), 'Protected source data changed'
    assert all(v['unchanged'] for v in security.values()), 'Security records changed'
    assert verification['intelligence_decisions']['all_original_rows_preserved']
    assert verification['events']['all_original_rows_preserved']
    metrics['protected_source_tables_unchanged']=len(protected)
    (directory/'verification.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'counts':overview['counts'],'measured_purchase_items':overview['purchase_intent_measured_items'],
        'embeddings':metrics['embedding_inventory'],'protected_tables':len(protected),'security_unchanged':True}))


if __name__=='__main__':main()
