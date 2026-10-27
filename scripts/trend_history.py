"""Offline bootstrap, validation and report data. Never invokes collection."""
import json
from collections import Counter
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import connect
from app import trend_history as trend


def main():
    folder=Path('artifacts/trend-history-v1');folder.mkdir(parents=True,exist_ok=True)
    with connect() as con:
        added=trend.import_history(con);assert trend.import_history(con)==0
        overview=trend.overview(con);details={}
        for row in overview['targets']:
            details[f"{row['target_type']}:{row['target_id']}"]=trend.summarize(trend.snapshots(con,row['target_type'],row['target_id']),row['target_type'])
        video=[r for r in overview['targets'] if r['target_type']=='VIDEO']
        distribution=Counter('1' if r['observations']==1 else '2' if r['observations']==2 else '3+' for r in video)
        spans=[v['time_span_seconds'] for v in video if v['time_span_seconds'] is not None]
        change_ready=[]
        cp=trend.settings()['change_point']
        for target,detail in details.items():
            for metric,points in detail['series'].items():
                if len(points)>=cp['minimum_points']:
                    span=(trend.datetime.fromisoformat(points[-1]['observed_at'])-trend.datetime.fromisoformat(points[0]['observed_at'])).total_seconds()
                    if span>=cp['minimum_span_hours']*3600:change_ready.append([target,metric])
        result={'added_this_run':added,'overview':overview,'details':details,'video_observation_distribution':dict(distribution),
            'videos_without_history':con.execute('SELECT count(*) FROM videos WHERE id NOT IN (SELECT video_id FROM trend_snapshots WHERE target_type=\'VIDEO\')').fetchone()[0],
            'average_video_span_seconds':sum(spans)/len(spans) if spans else None,'change_point_ready_series':change_ready,'idempotence_verified':True}
    before=sqlite3.connect(str(folder/'checkpoint.db'));after=sqlite3.connect('file:data/product_hunter.db?mode=ro',uri=True)
    preservation={}
    for (table,) in before.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        cols=','.join('"'+r[1]+'"' for r in before.execute(f'PRAGMA table_info("{table}")'))
        def rows(db):return sorted(json.dumps(list(r),default=str) for r in db.execute(f'SELECT {cols} FROM "{table}"'))
        preservation[table]=rows(before)==rows(after)
    assert all(ok for table,ok in preservation.items() if table not in ('events','system_state'))
    assert set(before.execute('SELECT * FROM events'))<=set(after.execute('SELECT * FROM events'))
    security={key:before.execute('SELECT * FROM system_state WHERE key=?',(key,)).fetchone()==after.execute('SELECT * FROM system_state WHERE key=?',(key,)).fetchone() for key in ('browser_security_stop','browser_security_history')}
    assert all(security.values());result.update(preservation=preservation,security_unchanged=security)
    (folder/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('overview','details','preservation')},ensure_ascii=True))
    print(json.dumps({'snapshots':overview['snapshots'],'targets':dict(Counter(r['target_type'] for r in overview['targets'])),
        'velocity_ready':dict(Counter(r['target_type'] for r in overview['targets'] if r['velocity_ready'])),
        'acceleration_ready':dict(Counter(r['target_type'] for r in overview['targets'] if r['acceleration_ready'])),
        'lifecycle':dict(Counter(r['lifecycle'] for r in overview['targets']))}))


if __name__=='__main__':main()
