"""Offline resolver. --apply persists only resolver columns/rows; no detection/browser."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.product_identity_resolver import resolve,records,compare,configuration


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--output',default='data/product_identity_resolver_report.json')
    args=parser.parse_args();path=ROOT/'data/product_hunter.db'
    con=sqlite3.connect(path if args.apply else path.as_uri()+'?mode=ro',uri=not args.apply)
    con.row_factory=sqlite3.Row;con.execute('PRAGMA foreign_keys=ON')
    if args.apply:
        with con:report=resolve(con)
    else:
        con.execute('PRAGMA query_only=ON');pairs=records(con)
        evaluated=[{'id':p['id'],**p['evidence']} for p in pairs]
        report={'resolver_version':configuration()['resolver']['version'],'pairs_evaluated':len(pairs),
          **{status:sum(p['semantic_result']==status for p in pairs) for status in ('different','insufficient','possible_same_product')},
          'pairs':evaluated,'possible_matches':[p for p in evaluated if p['semantic_result']=='possible_same_product'],
          'top_5':evaluated[:5]}
    unresolved=[dict(r) for r in con.execute('SELECT * FROM unresolved_product_phrases ORDER BY id')]
    target={r['normalized_phrase']:r for r in unresolved}
    if 'vacuum cleaner' in target and 'mini vacuum cleaner' in target:
        a,b=[{'id':str(target[k]['id']),'phrase':target[k]['raw_phrase'],'source':'unresolved_product_phrase',
                'video_id':target[k]['video_id'],'candidate_id':None} for k in ('vacuum cleaner','mini vacuum cleaner')]
        report['unresolved_comparison']=compare(a,b)
    report['mode']='offline_additive_resolver' if args.apply else 'read_only'
    report['security_stop']=dict(con.execute("SELECT * FROM system_state WHERE key='browser_security_stop'").fetchone())
    con.close()
    (ROOT/args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('pairs_evaluated','different','insufficient','possible_same_product')}))


if __name__=='__main__':main()
