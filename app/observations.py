"""SQLite enrichment repository. Callers own the transaction."""
import json
from html import escape
from html.parser import HTMLParser

from .extraction import STRUCTURED_FIELDS, METRIC_FIELDS, EXTRACTOR_VERSION, video_identity, legacy_url_fallback, parse_views, completeness, merge_evidence, capture_quality


class SnapshotSanitizer(HTMLParser):
    tags = {'article', 'div', 'span', 'p', 'a', 'strong', 'b', 'em', 'h2', 'h3', 'h4', 'section', 'figure', 'figcaption'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.blocked = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'form', 'textarea', 'template'):
            self.blocked += 1
        if self.blocked or tag not in self.tags:
            return
        attrs = [(k, v) for k, v in attrs if k in ('data-e2e', 'role') and v and len(v) <= 80]
        self.parts.append('<' + tag + ''.join(f' {k}="{escape(v, quote=True)}"' for k, v in attrs) + '>')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'form', 'textarea', 'template'):
            self.blocked = max(0, self.blocked - 1)
            return
        if not self.blocked and tag in self.tags:
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(escape(data))


def sanitize_snapshot(value):
    if not value:
        return None
    parser = SnapshotSanitizer()
    parser.feed(value)
    return ''.join(parser.parts)[:12000]


def prepared_fields(video, observed_at):
    try:
        canonical, strong_id = video_identity(video['video_url'])
    except ValueError:
        # Migration fallback only: preserve historical records even if their
        # original URL predates current validation. New payloads validate URLs.
        canonical, strong_id = legacy_url_fallback(video['video_url']), None
    raw = video.get('views_raw')
    if raw is None and isinstance(video.get('views'), str):
        raw = video['views']
    values = {field: video.get(field) for field in STRUCTURED_FIELDS}
    values.update(video_url=canonical, video_id=strong_id, views=parse_views(raw))
    evidence = {}
    for field, value in values.items():
        if value is None:
            continue
        supplied = video.get('field_evidence', {}).get(field)
        if supplied:
            evidence[field] = {**supplied, 'observed_at': observed_at}
        else:
            # Legacy rows had no method provenance: do not claim a reliable
            # creator/caption method retroactively. URL identity is verifiable.
            evidence[field] = {'value': value, 'confidence': 1.0 if field in ('video_url', 'video_id') else 0.0,
                               'source': 'search_card' if field in ('video_url', 'video_id') else 'heuristic_text',
                               'observed_at': observed_at}
        if field == 'views':
            evidence[field]['raw_value'] = raw
    for metric in METRIC_FIELDS[1:]:
        supplied = video.get('field_evidence', {}).get(metric)
        if supplied:
            evidence[metric] = {**supplied, 'observed_at': observed_at}
        values[metric] = video.get(metric)
    values.update(views_raw=raw, card_diagnostics=video.get('card_diagnostics'))
    return values, evidence


def save_capture(con, capture, capture_id, now, first_seen=None, legacy_id=None):
    existing = con.execute('SELECT new_count,updated_count FROM search_captures WHERE capture_id=?', (capture_id,)).fetchone()
    if existing:
        return existing['new_count'] or 0, existing['updated_count'] or 0
    version = capture['results'][0].get('extraction_version', 'search-dom-v1') if capture['results'] else EXTRACTOR_VERSION
    con.execute('INSERT INTO search_captures(capture_id,search_query,observed_at,extractor_version) VALUES (?,?,?,?) ON CONFLICT(capture_id) DO NOTHING',
                (capture_id, capture['query'], now, version))
    inserted = updated = 0
    for video in capture['results']:
        values, evidence = prepared_fields(video, now)
        row = con.execute('SELECT * FROM videos WHERE (source=? AND video_id=?) OR canonical_url=?',
                          ('tiktok', values['video_id'], values['video_url'])).fetchone()
        best = merge_evidence(json.loads(row['field_evidence_json']) if row else {}, evidence)
        effective = {field: best.get(field, {}).get('value') for field in STRUCTURED_FIELDS}
        if row:
            internal_id = row['id']
            con.execute('''UPDATE videos SET canonical_url=?, creator_username=?, creator_display_name=?, caption=?,
                thumbnail_url=?, last_seen_at=?, first_seen_at=?, field_evidence_json=? WHERE id=?''',
                (effective['video_url'], effective['creator_username'], effective['creator_display_name'], effective['caption'],
                 effective['thumbnail_url'], max(row['last_seen_at'], now), min(row['first_seen_at'], first_seen or now), json.dumps(best), internal_id))
            updated += 1
        else:
            cursor = con.execute('''INSERT INTO videos(source,video_id,canonical_url,creator_username,creator_display_name,
                caption,thumbnail_url,first_seen_at,last_seen_at,field_evidence_json) VALUES ('tiktok',?,?,?,?,?,?,?,?,?)''',
                (values['video_id'], values['video_url'], effective['creator_username'], effective['creator_display_name'],
                 effective['caption'], effective['thumbnail_url'], first_seen or now, now, json.dumps(best)))
            internal_id = cursor.lastrowid
            inserted += 1
        if 'first_search_query' in {r['name'] for r in con.execute('PRAGMA table_info(videos)')}:
            con.execute('UPDATE videos SET first_search_query=COALESCE(first_search_query,?),latest_search_query=? WHERE id=?',(capture['query'],capture['query'],internal_id))
        con.execute('''INSERT INTO search_observations(video_id,capture_id,search_query,search_position,observed_at,
            raw_visible_text,card_snapshot,extractor_version,extraction_completeness,fields_json,field_evidence_json,legacy_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(capture_id,video_id) DO NOTHING''',
            (internal_id, capture_id, capture['query'], video.get('search_position'), now, video.get('raw_visible_text'),
             sanitize_snapshot(video.get('card_snapshot')), video.get('extraction_version', 'search-dom-v1'),
             completeness(values), json.dumps(values), json.dumps(evidence), legacy_id))
    if 'visible_position' in {r['name'] for r in con.execute('PRAGMA table_info(search_observations)')}:
        con.execute('UPDATE search_observations SET visible_position=search_position WHERE capture_id=?',(capture_id,))
    if legacy_id is None:
        con.execute('UPDATE search_captures SET new_count=?,updated_count=? WHERE capture_id=?', (inserted, updated, capture_id))
    from .trend_history import record_search_observation
    for observation in con.execute('SELECT * FROM search_observations WHERE capture_id=?',(capture_id,)).fetchall():
        record_search_observation(con,observation)
    return inserted, updated


def migrate(con):
    # All inserts and the migration marker are in init_db's transaction. The
    # original video_observations table is retained as a read-only legacy archive.
    statements = [
        '''CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY)''',
        '''CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL CHECK(source='tiktok'),
            video_id TEXT, canonical_url TEXT NOT NULL UNIQUE, creator_username TEXT, creator_display_name TEXT,
            caption TEXT, thumbnail_url TEXT, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
            field_evidence_json TEXT NOT NULL, UNIQUE(source,video_id))''',
        '''CREATE TABLE IF NOT EXISTS search_captures (
            capture_id TEXT PRIMARY KEY, search_query TEXT NOT NULL, observed_at TEXT NOT NULL, extractor_version TEXT NOT NULL,
            new_count INTEGER, updated_count INTEGER)''',
        '''CREATE TABLE IF NOT EXISTS search_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL REFERENCES videos(id),
            capture_id TEXT NOT NULL, search_query TEXT NOT NULL, search_position INTEGER,
            observed_at TEXT NOT NULL, raw_visible_text TEXT, card_snapshot TEXT, extractor_version TEXT NOT NULL,
            extraction_completeness REAL NOT NULL CHECK(extraction_completeness BETWEEN 0 AND 1),
            fields_json TEXT NOT NULL, field_evidence_json TEXT NOT NULL, legacy_id INTEGER UNIQUE,
            UNIQUE(capture_id,video_id))''',
        '''CREATE TABLE IF NOT EXISTS video_detail_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, video_id INTEGER NOT NULL REFERENCES videos(id),
            command_id INTEGER NOT NULL UNIQUE, observed_at TEXT NOT NULL, extractor_version TEXT NOT NULL,
            raw_visible_text TEXT, card_snapshot TEXT, fields_json TEXT NOT NULL, field_evidence_json TEXT NOT NULL)''',
        'CREATE INDEX IF NOT EXISTS observations_video_time ON search_observations(video_id,observed_at DESC,id DESC)',
        'CREATE INDEX IF NOT EXISTS observations_capture ON search_observations(capture_id)',
    ]
    for statement in statements:
        con.execute(statement)
    columns = {row['name'] for row in con.execute('PRAGMA table_info(search_captures)')}
    for column in ('new_count', 'updated_count'):
        if column not in columns:
            con.execute(f'ALTER TABLE search_captures ADD COLUMN {column} INTEGER')
    # Previous command captures used exactly the same server timestamp for
    # first_seen_at and observed_at on inserts. Backfill from persisted evidence,
    # never from the current library total or a hardcoded example. Imported
    # legacy snapshots lack this history and deliberately retain null counters.
    con.execute('''UPDATE search_captures SET
        new_count=(SELECT COUNT(*) FROM search_observations o JOIN videos v ON v.id=o.video_id
            WHERE o.capture_id=search_captures.capture_id AND v.first_seen_at=o.observed_at),
        updated_count=(SELECT COUNT(*) FROM search_observations o JOIN videos v ON v.id=o.video_id
            WHERE o.capture_id=search_captures.capture_id AND v.first_seen_at<>o.observed_at)
        WHERE new_count IS NULL AND capture_id LIKE 'command:%' ''')
    if con.execute("SELECT 1 FROM schema_migrations WHERE name='search-enrichment-v1'").fetchone():
        return
    for row in con.execute('SELECT * FROM video_observations ORDER BY id').fetchall():
        video = dict(row)
        save_capture(con, {'query': row['search_query'], 'results': [video]}, f"legacy:{row['id']}",
                     row['last_seen_at'], row['first_seen_at'], row['id'])
    con.execute("INSERT INTO schema_migrations(name) VALUES ('search-enrichment-v1')")


def save_detail(con, detail, command_id, now):
    values, incoming = prepared_fields(detail, now)
    row = con.execute('SELECT * FROM videos WHERE source=? AND video_id=?', ('tiktok', values['video_id'])).fetchone()
    if not row:
        return False
    evidence = merge_evidence(json.loads(row['field_evidence_json']), incoming)
    effective = {field: evidence.get(field, {}).get('value') for field in STRUCTURED_FIELDS}
    con.execute('''UPDATE videos SET canonical_url=?,creator_username=?,creator_display_name=?,caption=?,
        thumbnail_url=?,last_seen_at=?,field_evidence_json=? WHERE id=?''',
        (effective['video_url'], effective['creator_username'], effective['creator_display_name'], effective['caption'],
         effective['thumbnail_url'], max(row['last_seen_at'], now), json.dumps(evidence), row['id']))
    con.execute('''INSERT INTO video_detail_observations(video_id,command_id,observed_at,extractor_version,
        raw_visible_text,card_snapshot,fields_json,field_evidence_json) VALUES (?,?,?,?,?,?,?,?)''',
        (row['id'], command_id, now, detail['extraction_version'], detail.get('raw_visible_text'),
         sanitize_snapshot(detail.get('card_snapshot')), json.dumps(values), json.dumps(incoming)))
    con.execute('INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)',
                (now, 'INFO', 'detail', f"Video detail #{command_id} stored for {values['video_id']} (READ ONLY)"))
    return True


def recent(con, limit):
    total = con.execute('SELECT COUNT(*) FROM videos').fetchone()[0]
    rows = con.execute('''SELECT v.*,o.id AS observation_id,o.capture_id,o.search_query,o.search_position,
        o.observed_at,o.raw_visible_text,o.card_snapshot,o.extractor_version,o.extraction_completeness,o.fields_json
        FROM videos v JOIN search_observations o ON o.id=(SELECT id FROM search_observations
        WHERE video_id=v.id ORDER BY observed_at DESC,id DESC LIMIT 1)
        ORDER BY v.last_seen_at DESC,v.id DESC LIMIT ?''', (limit,)).fetchall()
    items = []
    for row in rows:
        evidence = json.loads(row['field_evidence_json'])
        values = json.loads(row['fields_json'])
        item = {key: row[key] for key in ('id', 'source', 'video_id', 'canonical_url', 'creator_username',
                'creator_display_name', 'caption', 'thumbnail_url', 'first_seen_at', 'last_seen_at', 'observation_id',
                'capture_id', 'search_query', 'search_position', 'raw_visible_text', 'card_snapshot', 'extractor_version', 'extraction_completeness')}
        item.update(video_url=row['canonical_url'], views=evidence.get('views', {}).get('value'),
                    views_raw=evidence.get('views', {}).get('raw_value'), field_evidence=evidence,
                    collected_at=row['observed_at'], extraction_version=row['extractor_version'],
                    likes=values.get('likes'), comments_count=values.get('comments_count'), shares=values.get('shares'),
                    favorites=values.get('favorites'), card_diagnostics=values.get('card_diagnostics'))
        items.append(item)
    return {'total': total, 'items': items}


def quality(con):
    library_total = con.execute('SELECT COUNT(*) FROM videos').fetchone()[0]
    latest = con.execute('SELECT * FROM search_captures ORDER BY rowid DESC LIMIT 1').fetchone()
    if not latest:
        return {**capture_quality([]), 'capture_id': None, 'query': None, 'observed_at': None, 'extractor_version': None,
                'library_total': library_total, 'current_capture': 0, 'new_this_capture': 0, 'updated_duplicates': 0}
    rows = con.execute('SELECT fields_json FROM search_observations WHERE capture_id=?', (latest['capture_id'],)).fetchall()
    metrics = capture_quality([json.loads(row['fields_json']) for row in rows])
    metrics['thresholds_met'] = metrics['thresholds_met'] and latest['extractor_version'] == EXTRACTOR_VERSION
    return {**metrics, 'library_total': library_total, 'current_capture': metrics['total'],
            'new_this_capture': latest['new_count'], 'updated_duplicates': latest['updated_count'], 'capture_id': latest['capture_id'],
            'query': latest['search_query'], 'observed_at': latest['observed_at'], 'extractor_version': latest['extractor_version']}
