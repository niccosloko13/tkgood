"""Local temporal evidence. No collector, provider, Gold access or identity mutation.

Counts of first-observed samples measure local coverage, not publication or sales.
No interpolation, resampling, counter carry-forward or fabricated baseline.
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

POLICY = Path(__file__).resolve().parents[1]/'config/trend_history.json'
METRICS = ('views','likes','comments','shares','favorites','known_video_count',
           'unique_creators_known','purchase_intent_count','purchase_intent_unique_authors','comment_sample_size')


def settings():return json.loads(POLICY.read_text(encoding='utf-8'))


def stamp(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('Timezone required')
    return parsed.astimezone(timezone.utc).isoformat()


def migrate(con):
    con.execute('''CREATE TABLE IF NOT EXISTS trend_snapshots (
      id INTEGER PRIMARY KEY, target_type TEXT NOT NULL, target_id TEXT NOT NULL,
      observed_at TEXT NOT NULL, video_id INTEGER REFERENCES videos(id),
      product_reference TEXT, source TEXT NOT NULL, payload_hash TEXT NOT NULL,
      payload_json TEXT NOT NULL, coverage_json TEXT NOT NULL,
      UNIQUE(target_type,target_id,observed_at,source,payload_hash))''')
    con.execute('''CREATE TABLE IF NOT EXISTS trend_snapshot_sources (
      source_key TEXT PRIMARY KEY,snapshot_id INTEGER NOT NULL REFERENCES trend_snapshots(id))''')
    con.execute('CREATE INDEX IF NOT EXISTS trend_target_time ON trend_snapshots(target_type,target_id,observed_at)')


def record_trend_snapshot(con, *, target_type, target_id, observed_at, source,
                          metrics, coverage, source_key, video_id=None, product_reference=None):
    """Future collection contract; caller owns transaction and supplies observed data.

    A stable source_key identifies the actual observation, not an invocation.
    Missing metrics stay null. An altered payload for an existing source is rejected.
    """
    if target_type not in ('VIDEO','PRODUCT_ENTITY','CANDIDATE','CATEGORY','SUBCATEGORY','PRODUCT_FAMILY'):raise ValueError('Unknown target type')
    if not source or not source_key or not str(target_id):raise ValueError('Provenance required')
    at=stamp(observed_at);payload={k:metrics.get(k) for k in METRICS}
    if set(metrics)-set(METRICS):raise ValueError('Unknown metric')
    for value in payload.values():
        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):raise ValueError('Metrics must be finite nonnegative numbers or null')
    encoded=json.dumps(payload,sort_keys=True);digest=hashlib.sha256(encoded.encode()).hexdigest()
    old=con.execute('SELECT s.* FROM trend_snapshot_sources p JOIN trend_snapshots s ON s.id=p.snapshot_id WHERE p.source_key=?',(source_key,)).fetchone()
    if old:
        if (old['target_type'],old['target_id'],old['observed_at'],old['source'],old['payload_hash'])!=(target_type,str(target_id),at,source,digest):raise ValueError('Source observation changed; explicit versioned correction required')
        if json.loads(old['coverage_json'])!=coverage:raise ValueError('Source coverage changed; explicit versioned correction required')
        return old['id']
    con.execute('''INSERT OR IGNORE INTO trend_snapshots(target_type,target_id,observed_at,video_id,product_reference,source,payload_hash,payload_json,coverage_json) VALUES(?,?,?,?,?,?,?,?,?)''',
                (target_type,str(target_id),at,video_id,product_reference,source,digest,encoded,json.dumps(coverage,sort_keys=True)))
    sid=con.execute('SELECT id FROM trend_snapshots WHERE target_type=? AND target_id=? AND observed_at=? AND source=? AND payload_hash=?',(target_type,str(target_id),at,source,digest)).fetchone()[0]
    con.execute('INSERT INTO trend_snapshot_sources VALUES (?,?)',(source_key,sid))
    return sid


def snapshots(con,kind,target):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='trend_snapshots'").fetchone():return []
    rows=[{**dict(r),'metrics':json.loads(r['payload_json']),'coverage':json.loads(r['coverage_json'])} for r in con.execute('SELECT * FROM trend_snapshots WHERE target_type=? AND target_id=? ORDER BY observed_at,id',(kind,str(target)))]
    sources={}
    for r in con.execute('SELECT p.snapshot_id,p.source_key FROM trend_snapshot_sources p JOIN trend_snapshots s ON s.id=p.snapshot_id WHERE s.target_type=? AND s.target_id=?',(kind,str(target))):sources.setdefault(r['snapshot_id'],[]).append(r['source_key'])
    for r in rows:r['source_keys']=sources.get(r['id'],[])
    return rows


def metric_series(rows,metric):
    grouped={}
    for r in rows:
        value=r['metrics'].get(metric)
        if value is not None:grouped.setdefault(r['observed_at'],[]).append((value,r['id']))
    points=[];conflicts=[]
    for at,values in sorted(grouped.items()):
        if len({v for v,i in values})>1:conflicts.append(at);continue
        points.append({'observed_at':at,'value':values[0][0],'evidence_ids':[i for v,i in values]})
    return points,conflicts


def rates(points,metric):
    policy=settings();unit_hours=metric in ('views','likes','comments','shares','favorites')
    seconds=3600 if unit_hours else 86400;unit='per_hour' if unit_hours else 'per_day'
    velocities=[]
    if len(points)>=policy['velocity_min_points']:
        for a,b in zip(points,points[1:]):
            duration=(datetime.fromisoformat(b['observed_at'])-datetime.fromisoformat(a['observed_at'])).total_seconds()
            if duration<=0:continue
            delta=b['value']-a['value']
            velocities.append(dict(value=delta/duration*seconds,unit=unit,from_value=a['value'],to_value=b['value'],from_at=a['observed_at'],to_at=b['observed_at'],duration_seconds=duration,
                evidence_ids=a['evidence_ids']+b['evidence_ids'],reason_codes=['OBSERVED_COUNTER_DECREASE_POSSIBLE_CORRECTION'] if delta<0 else ['OBSERVED_DELTA']))
    acceleration={'status':'INSUFFICIENT_HISTORY','value':None}
    if len(points)>=policy['acceleration_min_points'] and len(velocities)>=2:
        a,b=velocities[-2:];delta=b['value']-a['value']
        tolerance=max(policy['stable_absolute_tolerance'],abs(a['value'])*policy['stable_relative_tolerance'])
        midpoint_distance=(a['duration_seconds']+b['duration_seconds'])/2
        acceleration=dict(status='STABLE' if abs(delta)<=tolerance else 'ACCELERATING' if delta>0 else 'DECELERATING',value=delta/midpoint_distance*seconds,unit=unit+'_squared',previous_velocity=a['value'],current_velocity=b['value'],evidence_ids=list(dict.fromkeys(a['evidence_ids']+b['evidence_ids'])))
    return {'status':'measured' if velocities else 'INSUFFICIENT_HISTORY','intervals':velocities,'latest':velocities[-1] if velocities else None,'acceleration':acceleration}


def summarize(rows,kind='VIDEO'):
    policy=settings();series={};velocities={};conflicts={}
    for metric in METRICS:
        points,bad=metric_series(rows,metric);series[metric]=points;conflicts[metric]=bad;velocities[metric]=rates(points,metric)
    times=sorted({r['observed_at'] for r in rows})
    span=(datetime.fromisoformat(times[-1])-datetime.fromisoformat(times[0])).total_seconds() if len(times)>1 else None
    videos=max((r['metrics'].get('known_video_count') or 0 for r in rows),default=0) or (1 if rows and kind=='VIDEO' else None)
    creators=max((r['metrics'].get('unique_creators_known') or 0 for r in rows),default=0) or (len({r['coverage']['creator'] for r in rows if r['coverage'].get('creator')}) if kind=='VIDEO' else None) or None
    duplicate_dependency=1-len(rows)/sum(max(1,len(r.get('source_keys',[]))) for r in rows) if rows else None
    creator_coverage=rows[-1]['coverage'].get('creator_coverage') if rows else None
    q=policy['quality'];good=len(times)>=q['observations'] and (span or 0)>=q['span_hours']*3600 and (videos or 0)>=q['videos'] and (creators or 0)>=q['creators'] and not any(conflicts.values()) and (duplicate_dependency or 0)<=q['maximum_duplicate_dependency'] and creator_coverage is not None and creator_coverage>=q['minimum_creator_coverage']
    quality={'status':'measured' if good else 'partial' if rows else 'insufficient_data','strength':'HIGH' if good else 'LOW' if rows else None,
             'number_of_observations':len(times),'time_span_seconds':span,'unique_videos':videos,'unique_creators':creators,
             'duplicate_dependency':duplicate_dependency,'creator_coverage':creator_coverage,'source_coverage':sorted({r['source'] for r in rows}),
             'reason_codes':(['LOCAL_MULTISOURCE_COVERAGE'] if good else ['LIMITED_LOCAL_COVERAGE'])+(['SINGLE_CREATOR_DEPENDENCY'] if creators==1 else []),
             'coverage':'Known sample; not market or platform-wide activity'}
    latest=lambda name:velocities[name]['latest']
    valid=[v for v in velocities.values() if v['latest']]
    momentum_metrics=[velocities[k] for k in ('views','comments','likes','shares','known_video_count','unique_creators_known') if velocities[k]['latest']]
    accelerating=any(v['acceleration']['status']=='ACCELERATING' for v in momentum_metrics)
    # Qualitative local momentum, never a weighted score or a sales assertion.
    changes=[v['latest']['value'] for v in momentum_metrics]
    mixed=any(v>0 for v in changes) and any(v<0 for v in changes)
    momentum='INSUFFICIENT_HISTORY' if not changes else 'EARLY_SIGNAL' if mixed else 'ACCELERATING' if accelerating else 'GROWING' if any(v>0 for v in changes) else 'DECLINING' if any(v<0 for v in changes) else 'STABLE'
    category_ready=kind not in ('CATEGORY','SUBCATEGORY','PRODUCT_FAMILY') or (len(times)>=policy['category']['observations'] and (span or 0)>=policy['category']['span_hours']*3600 and (videos or 0)>=policy['category']['videos'] and (creators or 0)>=policy['category']['creators'])
    if not category_ready:momentum='INSUFFICIENT_HISTORY'
    life='DISCOVERED' if rows else 'INSUFFICIENT_HISTORY'
    if momentum not in ('INSUFFICIENT_HISTORY','STABLE') and changes:
        life='EARLY_SIGNAL'
        lp=policy['lifecycle']
        broad=good and (videos or 0)>=lp['minimum_videos'] and (creators or 0)>=lp['minimum_creators'] and (span or 0)>=lp['minimum_span_hours']*3600
        if broad and category_ready and not mixed:life='ACCELERATING' if momentum=='ACCELERATING' else 'EMERGING' if momentum=='GROWING' else 'DECLINING' if momentum=='DECLINING' else life
    distribution=rows[-1]['coverage'].get('creator_video_counts') if rows else None
    concentration=max(distribution.values())/sum(distribution.values()) if distribution and sum(distribution.values()) else None
    return {'status':'partial' if valid else 'INSUFFICIENT_HISTORY','observations':len(rows),'time_span_seconds':span,'quality':quality,
        'series':series,'conflicting_timestamps':conflicts,'velocity':velocities,'momentum':momentum,'lifecycle':life,
        'creator_momentum':{'new_unique_creators':latest('unique_creators_known')['to_value']-latest('unique_creators_known')['from_value'] if latest('unique_creators_known') else None,
            'creator_arrival_rate':latest('unique_creators_known'),'creator_concentration':concentration,'single_creator_dependency':creators==1 if creators else None,'independence':'NOT_ESTABLISHED'},
        'purchase_intent_momentum':velocities['purchase_intent_unique_authors'],
        'reason_codes':['OBSERVED_LOCAL_HISTORY_ONLY','NO_INTERPOLATION','CAPTURE_TIME_NOT_PUBLICATION_TIME','COMMENT_SAMPLE_GROWTH_NOT_DEMAND_VELOCITY']+(['CONFLICTING_DIRECTIONS'] if mixed else [])}


def import_history(con):
    """Bootstrap original snapshots only. first_seen/last_seen are never metrics."""
    from .comments import consumer_signals_v2
    from .extraction import parse_views
    migrate(con);before=con.execute('SELECT count(*) FROM trend_snapshots').fetchone()[0]
    for table in ('search_observations','video_detail_observations'):
        for row in con.execute(f'SELECT * FROM {table} ORDER BY observed_at,id').fetchall():
            if table=='search_observations':
                record_search_observation(con,row)
                continue
            fields=json.loads(row['fields_json']);metrics={}
            for dest,key in [('views','views'),('likes','likes'),('comments','comments_count'),('shares','shares'),('favorites','favorites')]:
                value=fields.get(key)
                if isinstance(value,str):value=parse_views(value)
                metrics[dest]=value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0 else None
            creator=(fields.get('creator_username') or '').strip().lower().lstrip('@') or None
            record_trend_snapshot(con,target_type='VIDEO',target_id=row['video_id'],video_id=row['video_id'],observed_at=row['observed_at'],source=table,source_key=f"{table}:{row['id']}",metrics=metrics,
                coverage={'original_observation':row['id'],'creator':creator,'metrics_present':[k for k,v in metrics.items() if v is not None],'basis':'platform_counter_snapshot'})
    for sample in con.execute('SELECT * FROM comment_samples ORDER BY observed_at,id').fetchall():
        rows=[dict(r) for r in con.execute('SELECT * FROM comment_observations WHERE video_id=? AND observed_at<=? ORDER BY observed_at,id',(sample['video_id'],sample['observed_at']))]
        p=consumer_signals_v2(rows)
        record_trend_snapshot(con,target_type='VIDEO',target_id=sample['video_id'],video_id=sample['video_id'],observed_at=sample['observed_at'],source='comment_sample_cumulative',source_key=f"comment_sample:{sample['id']}",
            metrics={'purchase_intent_count':p['intent_comments'],'purchase_intent_unique_authors':p['unique_intent_authors'],'comment_sample_size':p['sample_size']},
            coverage={'sample_id':sample['id'],'evidence_ids':p['evidence_ids'],'raw_observations':p['raw_observations'],'unique_comments':p['sample_size'],'intent_authors':sorted({e['author'] for e in p['entries'] if e['author'] and set(e['types']) & set(p['intent_types'])}),
                'basis':'cumulative first-observed local comment sample; not all platform comments or actual demand arrival'})
    build_aggregates(con)
    return con.execute('SELECT count(*) FROM trend_snapshots').fetchone()[0]-before


def record_search_observation(con,row):
    """Collector hook: persists an observation; does not calculate trends."""
    from .extraction import parse_views
    try:stamp(row['observed_at'])
    except (ValueError,TypeError):
        # Preserve legacy observations without inventing their missing timezone.
        con.execute('INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)',
            (datetime.now(timezone.utc).isoformat(),'WARN','trend_skip',f"TREND_SKIPPED_AMBIGUOUS_TIMESTAMP search_observations:{row['id']}"))
        return None
    migrate(con);fields=json.loads(row['fields_json']);metrics={}
    for dest,key in [('views','views'),('likes','likes'),('comments','comments_count'),('shares','shares'),('favorites','favorites')]:
        value=fields.get(key)
        if isinstance(value,str):value=parse_views(value)
        metrics[dest]=value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0 else None
    creator=(fields.get('creator_username') or '').strip().lower().lstrip('@') or None
    return record_trend_snapshot(con,target_type='VIDEO',target_id=row['video_id'],video_id=row['video_id'],observed_at=row['observed_at'],source='search_observations',source_key=f"search_observations:{row['id']}",metrics=metrics,
        coverage={'original_observation':row['id'],'creator':creator,'metrics_present':[k for k,v in metrics.items() if v is not None],'basis':'platform_counter_snapshot'})


def build_aggregates(con):
    """Membership begins at evidence observation time, never backdated identity.

    Aggregate counters are null unless every member was observed at exactly that
    instant. No stale counters are carried forward. Candidate scope is unconfirmed.
    Category scopes are current-category retrospective cohorts, explicitly marked.
    """
    groups={}
    for r in con.execute('SELECT candidate_id,video_id,min(observed_at) AS at FROM product_candidate_evidence WHERE video_id IS NOT NULL GROUP BY candidate_id,video_id'):
        groups.setdefault(('CANDIDATE',str(r['candidate_id'])),{})[r['video_id']]=stamp(r['at'])
    for r in con.execute('SELECT o.product_id,o.video_id,d.created_at AS decision_at,e.created_at AS entity_at,r.observed_at AS review_at FROM intelligence_entity_observations o JOIN intelligence_decisions d ON d.id=o.decision_id JOIN intelligence_entities e ON e.id=o.product_id LEFT JOIN intelligence_reviews r ON r.decision_id=d.id'):
        at=max(stamp(r['entity_at']),stamp(r['review_at'] or r['decision_at']))
        members=groups.setdefault(('PRODUCT_ENTITY',str(r['product_id'])),{})
        members[r['video_id']]=min(members.get(r['video_id'],at),at)
    for r in con.execute('SELECT * FROM video_category_classifications WHERE primary_category IS NOT NULL'):
        history=snapshots(con,'VIDEO',r['video_id'])
        if not history:continue
        for kind,key in [('CATEGORY','primary_category'),('SUBCATEGORY','primary_subcategory'),('PRODUCT_FAMILY','product_family')]:
            if r[key]:groups.setdefault((kind,str(r['primary_category'])+'/'+str(r[key]) if kind!='CATEGORY' else str(r[key])),{})[r['video_id']]=history[0]['observed_at']
    for (kind,target),members in groups.items():
        histories={vid:snapshots(con,'VIDEO',vid) for vid in members}
        times=sorted(set(members.values()) | {r['observed_at'] for hist in histories.values() for r in hist if r['observed_at']>=members[r['video_id']]})
        for at in times:
            active={vid:hist for vid,hist in histories.items() if members[vid]<=at};creators={};authors=set();ids=[];metrics={'known_video_count':len(active)}
            exact={vid:[r for r in hist if r['observed_at']==at] for vid,hist in active.items()}
            for vid,hist in active.items():
                prior=[r for r in hist if r['observed_at']<=at]
                observed_creators=[r['coverage'].get('creator') for r in prior if r['coverage'].get('creator')]
                if observed_creators:creators[vid]=observed_creators[-1]
                for r in prior:
                    authors.update(r['coverage'].get('intent_authors',[]));ids.append(r['id'])
            metrics['unique_creators_known']=len(set(creators.values())) if creators else None
            metrics['purchase_intent_unique_authors']=len(authors) if any(r['source']=='comment_sample_cumulative' for h in active.values() for r in h if r['observed_at']<=at) else None
            for metric in ('views','likes','comments','shares','favorites'):
                totals=[]
                for hist in exact.values():
                    values={r['metrics'][metric] for r in hist if r['metrics'][metric] is not None}
                    if len(values)==1:totals.append(next(iter(values)))
                metrics[metric]=sum(totals) if len(totals)==len(active) and active else None
            record_trend_snapshot(con,target_type=kind,target_id=target,observed_at=at,source='local_cohort',source_key=f'cohort:{kind}:{target}:{at}',product_reference=f'{kind}:{target}',metrics=metrics,
                coverage={'basis':'current-category retrospective cohort' if kind in ('CATEGORY','SUBCATEGORY','PRODUCT_FAMILY') else 'unconfirmed candidate cohort' if kind=='CANDIDATE' else 'approved identity cohort',
                    'member_video_ids':sorted(active),'creator_video_counts':{creator:list(creators.values()).count(creator) for creator in set(creators.values())},'evidence_ids':sorted(set(ids)),
                    'creator_coverage':len(creators)/len(active) if active else None,'not_market_history':True})


def for_video(con,vid):return summarize(snapshots(con,'VIDEO',vid))


def overview(con):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='trend_snapshots'").fetchone():return {'snapshots':0,'targets':[]}
    targets=[]
    for r in con.execute('SELECT DISTINCT target_type,target_id FROM trend_snapshots ORDER BY target_type,target_id'):
        s=summarize(snapshots(con,r['target_type'],r['target_id']),r['target_type'])
        targets.append({'target_type':r['target_type'],'target_id':r['target_id'],'observations':s['observations'],
            'time_span_seconds':s['time_span_seconds'],'velocity_ready':any(v['latest'] for v in s['velocity'].values()),
            'acceleration_ready':any(v['acceleration']['status']!='INSUFFICIENT_HISTORY' for v in s['velocity'].values()),
            'momentum':s['momentum'],'lifecycle':s['lifecycle'],'quality':s['quality']})
    return {'snapshots':con.execute('SELECT count(*) FROM trend_snapshots').fetchone()[0],'targets':targets,
            'basis':'Persisted observations; local cohort and sampled intent growth are not market growth.'}


def change_points(points):
    """Optional ruptures adapter. Never imports/fits on short series."""
    p=settings()['change_point']
    if len(points)<p['minimum_points']:return {'status':'INSUFFICIENT_HISTORY','evidence':[]}
    span=(datetime.fromisoformat(points[-1]['observed_at'])-datetime.fromisoformat(points[0]['observed_at'])).total_seconds()
    if span<p['minimum_span_hours']*3600:return {'status':'INSUFFICIENT_HISTORY','evidence':[]}
    try:import ruptures
    except ImportError:return {'status':'ADAPTER_UNAVAILABLE','evidence':[]}
    import numpy as np
    boundaries=ruptures.Pelt(model='l2',min_size=p['minimum_segment']).fit(np.array([v['value'] for v in points])).predict(pen=p['penalty'])
    return {'status':'POSSIBLE_STRUCTURAL_CHANGE','evidence':[points[i-1] for i in boundaries if i<len(points)],'reason':'Possible change in sampled observation order; not proof of market change'}


class IncrementalAdapter:
    """Optional River consumer; stable snapshot IDs prevent repeated learning.

    Checkpoint is JSON of seen IDs; the caller also checkpoints its model. No model
    is trained by bootstrap, and this adapter does not synthesize missing features.
    """
    def __init__(self,model,seen=()):self.model=model;self.seen=set(seen)
    def consume(self,snapshot):
        if snapshot['id'] in self.seen:return False
        features={k:v for k,v in snapshot['metrics'].items() if v is not None}
        if not features:return False
        self.model.learn_one(features);self.seen.add(snapshot['id']);return True
    def checkpoint(self):return {'seen_snapshot_ids':sorted(self.seen)}
