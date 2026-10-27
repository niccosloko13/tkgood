"""Offline, deterministic opportunity intelligence over persisted local evidence.

This module never navigates, reads the browser, changes raw observations or
consults Gold Set labels.  Candidate membership is time-bounded by the stored
candidate evidence timestamp, which is also the backtest anti-leakage boundary.
"""
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'config' / 'trend_engine_v2.json').read_text(encoding='utf-8'))
VERSION = CONFIG['version']
METRICS = tuple(CONFIG['metric_names'])


def _stamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def _iso(value):
    return value.astimezone(timezone.utc).isoformat() if isinstance(value, datetime) else None


def _normal_query(value):
    return ' '.join(str(value or '').casefold().split())


def _numeric(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def migrate(con):
    con.execute('''CREATE TABLE IF NOT EXISTS top_opportunities (
        candidate_id INTEGER PRIMARY KEY REFERENCES product_candidates(id),
        engine_version TEXT NOT NULL, source_hash TEXT NOT NULL, computed_at TEXT NOT NULL,
        result_json TEXT NOT NULL
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS trend_change_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL REFERENCES product_candidates(id),
        event_type TEXT NOT NULL, prior_value TEXT, next_value TEXT NOT NULL,
        observed_at TEXT NOT NULL, source_hash TEXT NOT NULL, evidence_json TEXT NOT NULL,
        UNIQUE(candidate_id,event_type,next_value,source_hash)
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS prediction_checkpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL REFERENCES product_candidates(id),
        prediction_time TEXT NOT NULL, lifecycle TEXT NOT NULL, momentum TEXT NOT NULL,
        source_hash TEXT NOT NULL, evidence_snapshot_json TEXT NOT NULL,
        metrics_snapshot_json TEXT NOT NULL, why_snapshot_json TEXT NOT NULL,
        created_at TEXT NOT NULL, UNIQUE(candidate_id,prediction_time,source_hash)
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS prediction_evaluations (
        checkpoint_id INTEGER NOT NULL REFERENCES prediction_checkpoints(id), horizon_hours INTEGER NOT NULL,
        evaluated_at TEXT NOT NULL, result TEXT NOT NULL CHECK(result IN ('GREW','STABLE','DECLINED','UNKNOWN')),
        evidence_json TEXT NOT NULL, PRIMARY KEY(checkpoint_id,horizon_hours)
    )''')
    con.execute('''CREATE TRIGGER IF NOT EXISTS prediction_checkpoint_immutable
        BEFORE UPDATE ON prediction_checkpoints BEGIN SELECT RAISE(ABORT,'Prediction checkpoints are immutable'); END''')
    con.execute('CREATE INDEX IF NOT EXISTS opportunity_change_candidate_time ON trend_change_events(candidate_id,observed_at)')


def _candidate_row(con, candidate_id):
    return con.execute('SELECT * FROM product_candidates WHERE id=?', (candidate_id,)).fetchone()


def _candidate_ids(con):
    return [r[0] for r in con.execute('SELECT id FROM product_candidates ORDER BY id')]


def _as_of_default(con):
    row = con.execute('SELECT max(observed_at) FROM search_observations').fetchone()
    return _stamp(row[0]) if row and row[0] else datetime.now(timezone.utc)


def _members(con, candidate_id, as_of):
    """Candidate membership known at T0; never backdate membership in backtests."""
    return [r[0] for r in con.execute('''SELECT DISTINCT video_id FROM product_candidate_evidence
        WHERE candidate_id=? AND video_id IS NOT NULL AND observed_at<=?''', (candidate_id, _iso(as_of))) if r[0] is not None]


def _observations(con, candidate_id, as_of):
    members = _members(con, candidate_id, as_of)
    if not members:
        return []
    marks = ','.join('?' for _ in members)
    rows = con.execute(f'''SELECT o.*, v.creator_username AS video_creator FROM search_observations o
        JOIN videos v ON v.id=o.video_id WHERE o.video_id IN ({marks}) AND o.observed_at<=?
        ORDER BY o.observed_at,o.id''', (*members, _iso(as_of))).fetchall()
    out = []
    for row in rows:
        at = _stamp(row['observed_at'])
        if not at:
            continue
        try:
            fields = json.loads(row['fields_json'])
        except (TypeError, ValueError):
            fields = {}
        creator = str(fields.get('creator_username') or row['video_creator'] or '').strip().lower().lstrip('@') or None
        out.append({**dict(row), 'at': at, 'fields': fields, 'creator': creator})
    return out


def _metric_series(con, candidate_id, as_of):
    rows = con.execute('''SELECT id,observed_at,payload_json FROM trend_snapshots
        WHERE target_type='CANDIDATE' AND target_id=? AND observed_at<=? ORDER BY observed_at,id''',
        (str(candidate_id), _iso(as_of))).fetchall()
    series = {name: [] for name in METRICS}
    conflicts = {name: [] for name in METRICS}
    by_time = {name: defaultdict(list) for name in METRICS}
    for row in rows:
        at = _stamp(row['observed_at'])
        if not at:
            continue
        try:
            payload = json.loads(row['payload_json'])
        except (TypeError, ValueError):
            payload = {}
        for name in METRICS:
            value = _numeric(payload.get(name))
            if value is not None:
                by_time[name][at].append((value, row['id']))
    for name, grouped in by_time.items():
        for at, values in sorted(grouped.items()):
            if len({v for v, _ in values}) != 1:
                conflicts[name].append(_iso(at))
                continue
            series[name].append({'observed_at': _iso(at), 'value': values[0][0], 'evidence_ids': [v[1] for v in values]})
    return series, conflicts


def _rate(points):
    unavailable = {'status': 'INSUFFICIENT', 'value': None, 'unit': 'per_hour_squared', 'evidence_ids': []}
    if len(points) < 2:
        return {'status': 'INSUFFICIENT', 'latest': None, 'intervals': [], 'acceleration': unavailable, 'negative_delta': False}
    intervals = []
    for first, second in zip(points, points[1:]):
        a, b = _stamp(first['observed_at']), _stamp(second['observed_at'])
        elapsed = (b - a).total_seconds() / 3600 if a and b else 0
        if elapsed <= 0:
            continue
        delta = second['value'] - first['value']
        intervals.append({'value': delta / elapsed, 'unit': 'per_hour', 'from_at': first['observed_at'],
                          'to_at': second['observed_at'], 'from_value': first['value'], 'to_value': second['value'],
                          'elapsed_hours': elapsed, 'evidence_ids': first['evidence_ids'] + second['evidence_ids'],
                          'negative_delta': delta < 0})
    if not intervals:
        return {'status': 'INSUFFICIENT', 'latest': None, 'intervals': [], 'acceleration': unavailable, 'negative_delta': False}
    latest = intervals[-1]
    tolerance = max(CONFIG['velocity']['stable_absolute_tolerance'], abs(latest['value']) * CONFIG['velocity']['stable_relative_tolerance'])
    direction = 'STABLE' if abs(latest['value']) <= tolerance else 'RISING' if latest['value'] > 0 else 'FALLING'
    acceleration = {'status': 'INSUFFICIENT', 'value': None, 'unit': 'per_hour_squared', 'evidence_ids': []}
    if len(intervals) >= 2 and len(points) >= CONFIG['velocity']['acceleration_minimum_points']:
        prior, current = intervals[-2:]
        delta = current['value'] - prior['value']
        tolerance = max(CONFIG['velocity']['stable_absolute_tolerance'], abs(prior['value']) * CONFIG['velocity']['stable_relative_tolerance'])
        span = max((prior['elapsed_hours'] + current['elapsed_hours']) / 2, 1e-12)
        acceleration = {'status': 'STABLE' if abs(delta) <= tolerance else 'RISING' if delta > 0 else 'FALLING',
                        'value': delta / span, 'unit': 'per_hour_squared',
                        'evidence_ids': list(dict.fromkeys(prior['evidence_ids'] + current['evidence_ids']))}
    return {'status': direction, 'latest': latest, 'intervals': intervals, 'acceleration': acceleration,
            'negative_delta': any(item['negative_delta'] for item in intervals)}


def _quality(observations, captures, query_count, creator_count, span_hours):
    e = CONFIG['evidence']
    count = len(observations)
    if count < 2 or len(captures) < 2:
        return 'INSUFFICIENT'
    if (count >= e['high_minimum_observations'] and len(captures) >= e['high_minimum_captures'] and
            query_count >= e['high_minimum_query_spread'] and creator_count >= e['high_minimum_creator_spread'] and
            span_hours is not None and span_hours >= e['high_minimum_span_hours']):
        return 'HIGH'
    if count >= e['medium_minimum_observations'] and len(captures) >= e['medium_minimum_captures'] and query_count >= e['medium_minimum_query_spread']:
        return 'MEDIUM'
    return 'LOW'


def _saturation(observation_count, duplicate_density, creator_count, query_count, recent_new_query):
    p = CONFIG['saturation']
    if observation_count < p['minimum_observations']:
        return 'INSUFFICIENT'
    repeating_one_creator = creator_count <= 1
    narrow = query_count <= 1 or not recent_new_query
    if duplicate_density >= p['high_duplicate_density'] and repeating_one_creator and narrow:
        return 'HIGH'
    if duplicate_density >= p['medium_duplicate_density'] and (repeating_one_creator or narrow):
        return 'MEDIUM'
    return 'LOW'


def _summaries(velocity):
    directions = [v['status'] for v in velocity.values() if v['latest']]
    acceleration = [v['acceleration']['status'] for v in velocity.values() if v['acceleration']['status'] != 'INSUFFICIENT']
    velocity_summary = 'INSUFFICIENT' if not directions else 'RISING' if any(x == 'RISING' for x in directions) else 'FALLING' if directions and all(x == 'FALLING' for x in directions) else 'STABLE'
    acceleration_summary = 'INSUFFICIENT' if not acceleration else 'RISING' if any(x == 'RISING' for x in acceleration) else 'FALLING' if acceleration and all(x == 'FALLING' for x in acceleration) else 'STABLE'
    return velocity_summary, acceleration_summary


def _momentum(quality, captures, query_count, creator_count, velocity, acceleration, freshness_hours):
    if quality == 'INSUFFICIENT':
        return 'INSUFFICIENT'
    if (quality == 'HIGH' and query_count >= 3 and creator_count >= 2 and
            (velocity == 'RISING' or acceleration == 'RISING') and (freshness_hours is None or freshness_hours <= 48)):
        return 'HIGH'
    if len(captures) >= 2 and (query_count >= 2 or creator_count >= 2):
        return 'MEDIUM'
    return 'LOW'


def _lifecycle(observation_count, quality, momentum, query_count, creator_count, velocity, acceleration, saturation):
    limits = CONFIG['lifecycle']
    if observation_count < 2 or quality == 'INSUFFICIENT':
        return 'DISCOVERED'
    if saturation == 'HIGH':
        return 'SATURATED'
    if quality in ('MEDIUM', 'HIGH') and velocity == 'FALLING' and acceleration == 'FALLING':
        return 'DECLINING'
    if (quality == 'HIGH' and momentum == 'HIGH' and acceleration == 'RISING' and query_count >= limits['breakout_minimum_query_spread'] and creator_count >= limits['breakout_minimum_creator_spread'] and saturation == 'LOW'):
        return 'BREAKOUT'
    if (quality == 'HIGH' and query_count >= limits['mainstream_minimum_query_spread'] and creator_count >= limits['mainstream_minimum_creator_spread'] and velocity in ('RISING', 'STABLE')):
        return 'MAINSTREAM'
    if quality in ('MEDIUM', 'HIGH') and acceleration == 'RISING' and creator_count >= 2 and saturation != 'HIGH':
        return 'ACCELERATING'
    if quality in ('MEDIUM', 'HIGH') and (query_count >= limits['emerging_minimum_query_spread'] or creator_count >= 2) and saturation != 'HIGH':
        return 'EMERGING'
    return 'EARLY_SIGNAL'


def _why(data):
    reasons, risks, insufficient = [], [], []
    def add(target, code, text, evidence): target.append({'code': code, 'text': text, 'evidence_ids': sorted(set(evidence))})
    if data['query_spread'] >= 2:
        add(reasons, 'QUERY_SPREAD', f"Apareceu em {data['query_spread']} queries distintas.", data['observation_ids'])
    if data['creator_spread'] >= 2:
        add(reasons, 'CREATOR_SPREAD', f"Foi observado por {data['creator_spread']} creators distintos.", data['observation_ids'])
    if data['recurrence']['capture_count'] >= 2:
        add(reasons, 'RECURRENCE', f"Foi observado em {data['recurrence']['capture_count']} capturas distintas.", data['recurrence']['capture_evidence_ids'])
    if data['velocity_summary'] == 'RISING':
        ids = [x['latest']['evidence_ids'] for x in data['velocity'].values() if x['latest'] and x['status'] == 'RISING']
        add(reasons, 'VELOCITY_RISING', 'Ao menos uma métrica observada tem velocity positiva.', sum(ids, []))
    if data['acceleration_summary'] == 'RISING':
        ids = [x['acceleration']['evidence_ids'] for x in data['velocity'].values() if x['acceleration']['status'] == 'RISING']
        add(reasons, 'ACCELERATION_RISING', 'A velocity observada aumentou em uma janela subsequente.', sum(ids, []))
    if data['saturation'] == 'LOW':
        add(reasons, 'LOW_SATURATION', 'Os sinais locais de saturação permanecem baixos.', data['observation_ids'])
    if data['observation_count'] < 3:
        add(insufficient, 'FEW_OBSERVATIONS', 'Poucas observações persistidas.', data['observation_ids'])
    if not any(v['latest'] for v in data['velocity'].values()):
        add(insufficient, 'NO_NUMERIC_VELOCITY', 'Não há dois pontos numéricos válidos para calcular velocity.', [])
    if data['creator_spread'] < 2:
        add(insufficient, 'LOW_CREATOR_SPREAD', 'Creator spread ainda baixo.', data['observation_ids'])
    if data['quality'] in ('LOW', 'INSUFFICIENT'):
        add(insufficient, 'LIMITED_EVIDENCE', f"Qualidade de evidência: {data['quality']}.", data['observation_ids'])
    if data['saturation'] in ('MEDIUM', 'HIGH'):
        add(risks, 'SATURATION', f"Saturação local {data['saturation'].lower()} por repetição de resultados conhecidos.", data['observation_ids'])
    if any(v['negative_delta'] for v in data['velocity'].values()):
        add(risks, 'NEGATIVE_COUNTER_DELTA', 'Há delta negativo observado; pode refletir correção ou remoção de contador.', [])
    if data['freshness_hours'] is not None and data['freshness_hours'] > 48:
        add(risks, 'STALE', 'O candidato não apareceu nas últimas 48 horas da janela de dados.', data['observation_ids'])
    return reasons, risks, insufficient


def candidate_state(con, candidate_id, as_of=None):
    """Return a TopOpportunity-compatible state strictly using evidence at or before as_of."""
    migrate(con)
    as_of = _stamp(as_of) if as_of else _as_of_default(con)
    candidate = _candidate_row(con, candidate_id)
    if not candidate:
        raise KeyError(candidate_id)
    observations = _observations(con, candidate_id, as_of)
    observation_ids = [f"search_observations:{r['id']}" for r in observations]
    times = [r['at'] for r in observations]
    first, last = (min(times), max(times)) if times else (None, None)
    captures = sorted({r['capture_id'] for r in observations})
    queries = sorted({_normal_query(r['search_query']): r['search_query'] for r in observations}.values(), key=lambda x: _normal_query(x))
    creators = sorted({r['creator'] for r in observations if r['creator']})
    by_creator = defaultdict(set)
    for r in observations:
        if r['creator']:
            by_creator[r['creator']].add(r['capture_id'])
    series, conflicts = _metric_series(con, candidate_id, as_of)
    velocity = {metric: _rate(points) for metric, points in series.items()}
    velocity_summary, acceleration_summary = _summaries(velocity)
    span_hours = ((last - first).total_seconds() / 3600) if first and last else None
    unique_videos = len({r['video_id'] for r in observations})
    observation_count = len(observations)
    duplicate_density = (1 - unique_videos / observation_count) if observation_count else None
    late_cutoff = first + (last - first) / 2 if first and last else None
    early_queries = {_normal_query(r['search_query']) for r in observations if not late_cutoff or r['at'] <= late_cutoff}
    recent_new_query = any(_normal_query(r['search_query']) not in early_queries for r in observations if late_cutoff and r['at'] > late_cutoff)
    freshness_hours = ((as_of - last).total_seconds() / 3600) if last else None
    quality = _quality(observations, captures, len(queries), len(creators), span_hours)
    saturation = _saturation(observation_count, duplicate_density or 0, len(creators), len(queries), recent_new_query)
    momentum = _momentum(quality, captures, len(queries), len(creators), velocity_summary, acceleration_summary, freshness_hours)
    lifecycle = _lifecycle(observation_count, quality, momentum, len(queries), len(creators), velocity_summary, acceleration_summary, saturation)
    result = {
        'candidate_id': candidate_id, 'display_name': candidate['canonical_name'], 'engine_version': VERSION,
        'reference_time': _iso(as_of), 'first_seen': _iso(first), 'last_seen': _iso(last),
        'age_hours': ((as_of - first).total_seconds() / 3600) if first else None,
        'content_age_hours': None, 'content_age_reason': 'ORIGINAL_CONTENT_CREATE_TIME_UNAVAILABLE',
        'babi_detection_age_hours': ((as_of - first).total_seconds() / 3600) if first else None,
        'freshness_hours': freshness_hours, 'observation_count': observation_count, 'unique_video_count': unique_videos,
        'query_spread': len(queries), 'queries': queries, 'creator_spread': len(creators), 'creators': creators,
        'same_creator_recurrence': max((len(items) for items in by_creator.values()), default=0),
        'different_creator_spread': len(creators),
        'recurrence': {'capture_count': len(captures), 'distinct_times': len(set(times)),
                       'capture_evidence_ids': observation_ids, 'definition': 'distinct persisted capture_id; duplicates inside one capture do not increase recurrence'},
        'duplicate_density': duplicate_density, 'duplicate_density_unit': '1 - unique videos / observations',
        'saturation': saturation, 'evidence_quality': quality, 'quality': quality,
        'velocity': velocity, 'velocity_summary': velocity_summary, 'acceleration_summary': acceleration_summary,
        'lifecycle': lifecycle, 'momentum': momentum, 'series': series, 'conflicting_timestamps': conflicts,
        'observation_ids': observation_ids, 'trend_snapshot_ids': sorted({i for value in velocity.values() for point in value['intervals'] for i in point['evidence_ids']}),
        'last_updated': _iso(as_of),
        'limits': ['LOCAL_SEARCH_OBSERVATIONS_ONLY', 'NO_METRIC_CARRY_FORWARD', 'NO_GOLD_SET_INPUT', 'NOT_A_SALES_OR_MARKET_CLAIM']
    }
    result['why'], result['risks'], result['insufficient_signals'] = _why(result)
    return result


def _source_hash(result):
    source = {k: result[k] for k in ('candidate_id','reference_time','observation_ids','series','query_spread','queries','creator_spread','creators','recurrence')}
    return hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _event(con, candidate_id, event_type, before, after, state, source_hash):
    if before is None or before == after:
        return
    con.execute('''INSERT OR IGNORE INTO trend_change_events(candidate_id,event_type,prior_value,next_value,observed_at,source_hash,evidence_json)
        VALUES(?,?,?,?,?,?,?)''', (candidate_id, event_type, str(before), str(after), state['last_seen'] or state['reference_time'], source_hash,
                                    json.dumps({'observation_ids': state['observation_ids'], 'why': state['why']}, sort_keys=True)))


def _persist_prediction(con, state, source_hash, created_at):
    if state['lifecycle'] not in CONFIG['prediction']['eligible_lifecycles'] or state['momentum'] not in CONFIG['prediction']['eligible_momentum']:
        return None
    prediction_time = state['last_seen'] or state['reference_time']
    row = con.execute('''SELECT id FROM prediction_checkpoints WHERE candidate_id=? AND prediction_time=? AND source_hash=?''',
                      (state['candidate_id'], prediction_time, source_hash)).fetchone()
    if row:
        return row['id']
    cur = con.execute('''INSERT INTO prediction_checkpoints(candidate_id,prediction_time,lifecycle,momentum,source_hash,evidence_snapshot_json,metrics_snapshot_json,why_snapshot_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)''', (state['candidate_id'], prediction_time, state['lifecycle'], state['momentum'], source_hash,
           json.dumps({'observation_ids': state['observation_ids'], 'capture_count': state['recurrence']['capture_count'], 'query_spread': state['query_spread'], 'creator_spread': state['creator_spread']}, sort_keys=True),
           json.dumps({'velocity': state['velocity'], 'acceleration_summary': state['acceleration_summary'], 'saturation': state['saturation']}, sort_keys=True),
           json.dumps(state['why'], sort_keys=True), created_at))
    return cur.lastrowid


def recompute(con, as_of=None):
    """Idempotently build the read model without mutating observations/snapshots."""
    migrate(con)
    reference = _stamp(as_of) if as_of else _as_of_default(con)
    changed = events = predictions = 0
    for candidate_id in _candidate_ids(con):
        state = candidate_state(con, candidate_id, reference)
        digest = _source_hash(state)
        old = con.execute('SELECT source_hash,result_json FROM top_opportunities WHERE candidate_id=?', (candidate_id,)).fetchone()
        if old and old['source_hash'] == digest:
            continue
        old_result = json.loads(old['result_json']) if old else {}
        for key, event_name in [('lifecycle','LIFECYCLE_CHANGED'), ('momentum','MOMENTUM_CHANGED'), ('acceleration_summary','ACCELERATION_CHANGED'), ('saturation','SATURATION_CHANGED')]:
            before = old_result.get(key)
            _event(con, candidate_id, event_name, before, state[key], state, digest)
            events += int(before is not None and before != state[key])
        for key, event_name in [('query_spread','QUERY_SPREAD_INCREASED'), ('creator_spread','CREATOR_SPREAD_INCREASED')]:
            before = old_result.get(key)
            if before is not None and state[key] > before:
                _event(con, candidate_id, event_name, before, state[key], state, digest)
                events += 1
        con.execute('''INSERT INTO top_opportunities(candidate_id,engine_version,source_hash,computed_at,result_json) VALUES(?,?,?,?,?)
            ON CONFLICT(candidate_id) DO UPDATE SET engine_version=excluded.engine_version,source_hash=excluded.source_hash,computed_at=excluded.computed_at,result_json=excluded.result_json''',
            (candidate_id, VERSION, digest, _iso(reference), json.dumps(state, sort_keys=True, ensure_ascii=False)))
        changed += 1
        if _persist_prediction(con, state, digest, _iso(reference)):
            predictions += 1
    evaluate_predictions(con, reference)
    return {'reference_time': _iso(reference), 'changed': changed, 'events': events, 'prediction_checks': predictions}


def _outcome_at(con, checkpoint, horizon_hours, available_until):
    prediction_time = _stamp(checkpoint['prediction_time'])
    horizon = prediction_time + timedelta(hours=horizon_hours)
    if available_until < horizon:
        return 'UNKNOWN', {'reason': 'FUTURE_WINDOW_NOT_AVAILABLE', 'available_until': _iso(available_until)}
    baseline = json.loads(checkpoint['evidence_snapshot_json'])
    state = candidate_state(con, checkpoint['candidate_id'], horizon)
    baseline_ids = set(baseline['observation_ids'])
    future = [x for x in state['observation_ids'] if x not in baseline_ids]
    if not future:
        return 'UNKNOWN', {'reason': 'NO_FUTURE_CANDIDATE_OBSERVATION', 'horizon_end': _iso(horizon)}
    grew = state['query_spread'] > baseline['query_spread'] or state['creator_spread'] > baseline['creator_spread'] or state['recurrence']['capture_count'] > baseline['capture_count']
    # Counter decline only when the observed post-T0 summary consistently falls.
    falling = state['velocity_summary'] == 'FALLING' and state['acceleration_summary'] == 'FALLING'
    return ('GREW' if grew else 'DECLINED' if falling else 'STABLE'), {'future_observation_ids': future, 'horizon_end': _iso(horizon), 'state_at_horizon': {'query_spread': state['query_spread'], 'creator_spread': state['creator_spread'], 'velocity': state['velocity_summary'], 'acceleration': state['acceleration_summary']}}


def evaluate_predictions(con, available_until=None):
    migrate(con)
    available = _stamp(available_until) if available_until else _as_of_default(con)
    count = 0
    for checkpoint in con.execute('SELECT * FROM prediction_checkpoints ORDER BY id').fetchall():
        for horizon in CONFIG['prediction']['horizons_hours']:
            result, evidence = _outcome_at(con, checkpoint, horizon, available)
            old = con.execute('SELECT result FROM prediction_evaluations WHERE checkpoint_id=? AND horizon_hours=?', (checkpoint['id'], horizon)).fetchone()
            if not old:
                con.execute('INSERT INTO prediction_evaluations VALUES (?,?,?,?,?)', (checkpoint['id'], horizon, _iso(available), result, json.dumps(evidence, sort_keys=True)))
                count += 1
            elif old['result'] == 'UNKNOWN' and result != 'UNKNOWN':
                # UNKNOWN means the future window was absent, not a terminal
                # prediction result. The checkpoint itself remains immutable.
                con.execute('UPDATE prediction_evaluations SET evaluated_at=?,result=?,evidence_json=? WHERE checkpoint_id=? AND horizon_hours=?',
                            (_iso(available), result, json.dumps(evidence, sort_keys=True), checkpoint['id'], horizon))
                count += 1
    return count


def backtest(con):
    migrate(con)
    rows = con.execute('''SELECT p.momentum,e.result,count(*) n FROM prediction_checkpoints p
        JOIN prediction_evaluations e ON e.checkpoint_id=p.id WHERE e.horizon_hours=24 GROUP BY p.momentum,e.result''').fetchall()
    buckets = {name: Counter() for name in ('HIGH','MEDIUM','LOW')}
    for row in rows:
        buckets.setdefault(row['momentum'], Counter())[row['result']] = row['n']
    high = buckets['HIGH']; evaluated = sum(sum(v.values()) for v in buckets.values())
    return {'sample_size': evaluated, 'horizon_hours': 24, 'buckets': {k: dict(v) for k,v in buckets.items()},
            'high_candidates_that_grew': high['GREW'], 'high_candidates_that_failed': high['STABLE'] + high['DECLINED'],
            'medium_candidates_that_grew': buckets['MEDIUM']['GREW'], 'low_candidates_that_unexpectedly_grew': buckets['LOW']['GREW'],
            'precision_like_rate': (high['GREW'] / (high['GREW'] + high['STABLE'] + high['DECLINED'])) if (high['GREW'] + high['STABLE'] + high['DECLINED']) else None,
            'coverage': evaluated, 'insufficient_data_rate': (sum(v['UNKNOWN'] for v in buckets.values()) / evaluated) if evaluated else None,
            'note': 'Local evaluation coverage only; not formal statistical precision.'}


def opportunities(con, limit=20):
    migrate(con)
    rows = [json.loads(r['result_json']) for r in con.execute('SELECT result_json FROM top_opportunities')]
    lifecycle_rank = {'BREAKOUT': 7, 'ACCELERATING': 6, 'EMERGING': 5, 'EARLY_SIGNAL': 4, 'DISCOVERED': 3, 'MAINSTREAM': 2, 'SATURATED': 1, 'DECLINING': 0}
    momentum_rank = {'VERY_HIGH': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'INSUFFICIENT': 0}
    evidence_rank = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'INSUFFICIENT': 0}
    def rank(item):
        return (-lifecycle_rank[item['lifecycle']], -momentum_rank[item['momentum']], -evidence_rank[item['evidence_quality']], item['saturation'] == 'HIGH', item['freshness_hours'] or float('inf'), -item['query_spread'], -item['creator_spread'], item['candidate_id'])
    rows.sort(key=rank)
    top = [x for x in rows if x['evidence_quality'] in ('MEDIUM','HIGH') and x['lifecycle'] not in ('SATURATED','DECLINING')][:limit]
    selected = {x['candidate_id'] for x in top}
    watchlist = [x for x in rows if x['candidate_id'] not in selected][:limit]
    events = [dict(r) for r in con.execute('SELECT * FROM trend_change_events ORDER BY id DESC LIMIT 30')]
    for event in events:
        event['evidence'] = json.loads(event.pop('evidence_json'))
    return {'engine_version': VERSION, 'top_opportunities': top, 'watchlist': watchlist, 'trend_changes': events, 'backtest': backtest(con),
            'basis': 'Persisted local observations and timestamps only. Gold Set is excluded from input.'}
