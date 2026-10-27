"""Local-only additive semantic migration/report; never imports browser control.

Default is SQLite read-only. --apply writes ONLY the semantic tables/migration marker.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--output',default='data/product_semantics_report.json')
    args=parser.parse_args()
    path=ROOT/'data/product_hunter.db'
    con=sqlite3.connect(path if args.apply else path.as_uri()+'?mode=ro',uri=not args.apply)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    if args.apply:
        from app.candidate_semantics import migrate,refresh
        with con:
            migrate(con);refresh(con)
    else:con.execute('PRAGMA query_only=ON')
    from app.candidate_semantics import public_fields,product_signature
    items=[]
    for row in con.execute('SELECT * FROM product_candidates ORDER BY id'):
        c=dict(row)
        c.update(public_fields(con,c['id']))
        c['summary']=json.loads(c.pop('summary_json'))
        c['aliases']=[dict(r) for r in con.execute('SELECT * FROM product_candidate_aliases WHERE candidate_id=?',(c['id'],))]
        c['urls']=[dict(r) for r in con.execute('SELECT * FROM candidate_reference_urls WHERE candidate_id=?',(c['id'],))]
        c['evidence']=[dict(r) for r in con.execute('SELECT * FROM product_candidate_evidence WHERE candidate_id=?',(c['id'],))]
        c['videos']=[dict(r) for r in con.execute('''SELECT DISTINCT v.id,v.video_id,v.canonical_url,v.caption,c.username,c.profile_url
          FROM product_candidate_evidence e JOIN videos v ON v.id=e.video_id LEFT JOIN creators c ON c.creator_id=e.creator_id WHERE e.candidate_id=?''',(c['id'],))]
        items.append(c)
    unresolved=[{**dict(r),'signature':product_signature(r['raw_phrase'])} for r in con.execute('SELECT * FROM unresolved_product_phrases ORDER BY id')]
    report={'mode':'local_additive_migration' if args.apply else 'read_only','candidates':items,'unresolved_phrases':unresolved,
      'security_stop':dict(con.execute("SELECT * FROM system_state WHERE key='browser_security_stop'").fetchone()),
      'counts':{'library':con.execute('SELECT count(*) FROM videos').fetchone()[0],
        'candidates':len(items),'evidence':sum(len(c['evidence']) for c in items),
        'observed':sum(c['semantic_status']=='observed' for c in items),
        'concept_recurring':sum(c['semantic_status']=='concept_recurring' for c in items),
        'possible_same_product':sum(c['semantic_status']=='possible_same_product' for c in items),
        'product_matched':sum(c['semantic_status']=='product_matched' for c in items)}}
    con.close()
    (ROOT/args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report['counts']))


if __name__=='__main__':main()
