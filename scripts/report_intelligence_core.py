"""Read-only evidence export and original-table preservation verification."""
from pathlib import Path
import hashlib
import json
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import intelligence_core as core
from app.intelligence_evaluation import evaluate
from app.intelligence_embeddings import ResourceGovernor
from app.intelligence_index import ProductIndex


def digest(rows):
    rows=sorted(rows,key=lambda r:json.dumps(r,default=str))
    return hashlib.sha256(json.dumps(rows,ensure_ascii=False,default=str).encode()).hexdigest()


def main():
    directory=Path('artifacts/intelligence-core-consolidation')
    before=json.loads((directory/'before.json').read_text(encoding='utf-8'))
    con=sqlite3.connect('file:data/product_hunter.db?mode=ro',uri=True);con.row_factory=sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    preservation={}
    for table,old in before.items():
        columns=','.join('"'+c+'"' for c in old['columns'])
        rows=[list(r) for r in con.execute('SELECT '+columns+' FROM "'+table+'"')]
        preservation[table]={'before_rows':old['rows'],'after_rows':len(rows),'unchanged':digest(rows)==old['sha256']}
    original=sqlite3.connect(str(directory/'checkpoint.db'));original.row_factory=sqlite3.Row
    protected={}
    for key in ('browser_security_stop','browser_security_history'):
        a=original.execute('SELECT * FROM system_state WHERE key=?',(key,)).fetchone()
        b=con.execute('SELECT * FROM system_state WHERE key=?',(key,)).fetchone()
        protected[key]={'unchanged':(dict(a) if a else None)==(dict(b) if b else None),'current':dict(b) if b else None}
    result={'overview':core.overview(con),'evaluation':evaluate(con),'preservation':preservation,'security':protected,
            'inventory':{t:con.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('videos','product_candidates','visual_image_assets','visual_product_evidence','visual_product_search_evidence','intelligence_entities','intelligence_matches','intelligence_embeddings')},
            'current_reason_counts':[dict(r) for r in con.execute('SELECT reason_code,count(*) AS count FROM intelligence_decisions WHERE id IN (SELECT max(id) FROM intelligence_decisions GROUP BY video_id) GROUP BY reason_code')],
            'category_distribution':[dict(r) for r in con.execute('SELECT primary_category,category_status,count(*) AS count FROM video_category_classifications WHERE id IN (SELECT max(id) FROM video_category_classifications GROUP BY video_id) GROUP BY primary_category,category_status')],
            'new_tables':[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") if r[0] not in before]}
    (directory/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'inventory':result['inventory'],'current_decisions':result['overview']['counts'],
        'changed_existing_tables':[t for t,v in preservation.items() if not v['unchanged']],
        'security_preserved':all(v['unchanged'] for v in protected.values())},indent=2))


if __name__=='__main__':main()
