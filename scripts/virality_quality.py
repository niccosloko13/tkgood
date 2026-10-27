"""Bounded offline pilot and idempotent dimension snapshots; never runs Identity."""
from pathlib import Path
import json
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import connect
from app.intelligence_core import latest
from app.intelligence_signals import for_video,persist


def main():
    folder=Path('artifacts/virality-quality-v1');folder.mkdir(parents=True,exist_ok=True)
    with connect() as con:
        states={r['video_id']:r['status'] for r in latest(con)}
        pilot=list(dict.fromkeys([1,3,18]+[v for v,s in states.items() if s=='REVIEW']))
        results={}
        for vid in pilot:
            results[vid]=for_video(con,vid,states[vid]);persist(con,vid,results[vid])
        for vid in states:
            if vid not in results:results[vid]=for_video(con,vid,states[vid]);persist(con,vid,results[vid])
        count=con.execute('SELECT count(*) FROM intelligence_dimension_snapshots').fetchone()[0]
        for vid,result in results.items():persist(con,vid,result)
        assert con.execute('SELECT count(*) FROM intelligence_dimension_snapshots').fetchone()[0]==count
        result={'pilot':pilot,'identity_counts':{s:list(states.values()).count(s) for s in ('AUTO','REVIEW','UNRESOLVED')},'items':results,'snapshots':count,'idempotence_verified':True}
    before=sqlite3.connect(str(folder/'checkpoint.db'));after=sqlite3.connect('file:data/product_hunter.db?mode=ro',uri=True)
    protection={}
    for (table,) in before.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        columns=','.join('"'+r[1]+'"' for r in before.execute(f'PRAGMA table_info("{table}")'))
        def rows(db):return sorted(json.dumps(list(r),default=str) for r in db.execute(f'SELECT {columns} FROM "{table}"'))
        protection[table]=rows(before)==rows(after)
    # Backend heartbeat/event append is permitted; every domain table must match.
    assert all(ok for table,ok in protection.items() if table not in ('system_state','events'))
    security={}
    for key in ('browser_security_stop','browser_security_history'):
        old=before.execute('SELECT * FROM system_state WHERE key=?',(key,)).fetchone()
        new=after.execute('SELECT * FROM system_state WHERE key=?',(key,)).fetchone()
        security[key]=old==new
    assert all(security.values())
    result.update(protected_tables=protection,security_unchanged=security)
    (folder/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('items','protected_tables')}))


if __name__=='__main__':main()
