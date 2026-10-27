import json
import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH
from .observations import migrate as migrate_observations, save_capture, save_detail, recent, quality
from .comments import migrate as migrate_comments, save_sample
from .creators import migrate as migrate_creators, save_profile


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        with con:
            yield con
    finally:
        con.close()


def init_db():
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                level TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                market TEXT NOT NULL,
                mode TEXT NOT NULL,
                max_videos INTEGER NOT NULL,
                read_comments INTEGER NOT NULL,
                capture_evidence INTEGER NOT NULL,
                discover_related INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bridge_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('SEARCH','READ_SEARCH_RESULTS','READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE','DISCOVER_MORE_RESULTS')),
                query TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING','DISPATCHED','SUCCEEDED','FAILED','EXPIRED')),
                extension_id TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS video_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL DEFAULT 'tiktok' CHECK(source='tiktok'),
                search_query TEXT NOT NULL,
                video_url TEXT NOT NULL UNIQUE,
                creator_username TEXT, creator_display_name TEXT, caption TEXT,
                views TEXT, likes TEXT, comments_count TEXT, shares TEXT,
                collected_at TEXT NOT NULL, first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL, raw_visible_text TEXT,
                extraction_version TEXT NOT NULL
            );
            """
        )
        # SQLite cannot widen an existing CHECK constraint with ALTER COLUMN.
        # Rebuild only this table, preserving existing commands and their IDs.
        con.execute('BEGIN IMMEDIATE')
        sql = con.execute("SELECT sql FROM sqlite_master WHERE name='bridge_commands'").fetchone()[0]
        if 'DISCOVER_MORE_RESULTS' not in sql or 'WAITING_FOR_VISIBLE_BROWSER' in sql:
            con.execute("""CREATE TABLE bridge_commands_v5 (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, type TEXT NOT NULL CHECK(type IN ('SEARCH','READ_SEARCH_RESULTS','READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE','DISCOVER_MORE_RESULTS')),
                query TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PENDING','DISPATCHED','SUCCEEDED','FAILED','EXPIRED')),
                extension_id TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', result_hash TEXT NOT NULL DEFAULT '', options_json TEXT NOT NULL DEFAULT '{}',ready_at TEXT)""")
            columns = ['id','created_at','updated_at','type','query','status','extension_id','detail']
            if 'result_hash' in {row['name'] for row in con.execute('PRAGMA table_info(bridge_commands)')}:
                columns.append('result_hash')
            if 'options_json' in {row['name'] for row in con.execute('PRAGMA table_info(bridge_commands)')}:
                columns.append('options_json')
            if 'ready_at' in {row['name'] for row in con.execute('PRAGMA table_info(bridge_commands)')}:
                columns.append('ready_at')
            names = ','.join(columns)
            selection = ','.join("CASE WHEN status='WAITING_FOR_VISIBLE_BROWSER' THEN 'FAILED' ELSE status END" if c=='status' else c for c in columns)
            con.execute(f'INSERT INTO bridge_commands_v5({names}) SELECT {selection} FROM bridge_commands')
            if 'ready_at' not in columns:
                con.execute('UPDATE bridge_commands_v5 SET ready_at=created_at')
            con.execute('DROP TABLE bridge_commands')
            con.execute('ALTER TABLE bridge_commands_v5 RENAME TO bridge_commands')
        if 'result_hash' not in {row['name'] for row in con.execute('PRAGMA table_info(bridge_commands)')}:
            con.execute("ALTER TABLE bridge_commands ADD COLUMN result_hash TEXT NOT NULL DEFAULT ''")
        migrate_observations(con)
        if 'options_json' not in {row['name'] for row in con.execute('PRAGMA table_info(bridge_commands)')}:
            con.execute("ALTER TABLE bridge_commands ADD COLUMN options_json TEXT NOT NULL DEFAULT '{}'")
        if 'ready_at' not in {row['name'] for row in con.execute('PRAGMA table_info(bridge_commands)')}:
            con.execute("ALTER TABLE bridge_commands ADD COLUMN ready_at TEXT")
            con.execute("UPDATE bridge_commands SET ready_at=created_at")
        migrate_comments(con)
        migrate_creators(con)
        from .product_detection import migrate as migrate_products
        migrate_products(con)
        from .discovery import migrate as migrate_discovery
        migrate_discovery(con)
        from .enrichment import migrate as migrate_enrichment
        migrate_enrichment(con)
        from .candidate_semantics import migrate as migrate_semantics
        migrate_semantics(con)
        from .product_identity_resolver import migrate as migrate_identity_resolver
        migrate_identity_resolver(con)
        from .gold_set import migrate as migrate_gold_set
        migrate_gold_set(con)
        from .category_intelligence import migrate as migrate_categories
        migrate_categories(con)
        from .visual_identification import migrate as migrate_visual_identification
        migrate_visual_identification(con)
        from .intelligence_core import migrate as migrate_intelligence
        migrate_intelligence(con)
        from .trend_history import migrate as migrate_trend
        migrate_trend(con)
        from .safe_collection import migrate as migrate_safe_collection
        migrate_safe_collection(con)
        from .target_safety import migrate as migrate_target_safety
        migrate_target_safety(con)
        from .selective_enrichment import migrate as migrate_selective
        migrate_selective(con)
        from .manual_captcha_recovery import migrate as migrate_manual_captcha
        migrate_manual_captcha(con)
        from .collection_mode import migrate as migrate_collection_mode
        migrate_collection_mode(con)
        from .search_intelligence import migrate as migrate_search_only
        migrate_search_only(con)
        from .trend_engine_v2 import migrate as migrate_trend_engine_v2
        migrate_trend_engine_v2(con)
        from .viral_products_mission import migrate as migrate_viral_products_mission
        migrate_viral_products_mission(con)
        from .recency_intelligence import migrate as migrate_recency_intelligence
        migrate_recency_intelligence(con)
        from .market_radar.repository import migrate as migrate_market_radar
        migrate_market_radar(con)
        con.execute("UPDATE discovery_sessions SET status='FAILED',stop_reason='error',stop_detail='Legacy paused command retired; start a new operation' WHERE status='WAITING_FOR_VISIBLE_BROWSER'")


def log_event(event_type: str, message: str, level: str = "INFO"):
    with connect() as con:
        con.execute(
            "INSERT INTO events(created_at, level, event_type, message) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), level, event_type, message),
        )


def recent_events(limit: int = 50):
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def create_mission(
    market: str,
    mode: str,
    max_videos: int,
    read_comments: bool,
    capture_evidence: bool,
    discover_related: bool,
):
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        if maintenance_active(con):
            from fastapi import HTTPException
            raise HTTPException(409, 'Development maintenance in progress')
        cur = con.execute(
            """
            INSERT INTO missions(
                created_at, status, market, mode, max_videos,
                read_comments, capture_evidence, discover_related
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                "PENDING",
                market,
                mode,
                max_videos,
                int(read_comments),
                int(capture_evidence),
                int(discover_related),
            ),
        )
        return cur.lastrowid


def latest_mission():
    with connect() as con:
        row = con.execute(
            "SELECT * FROM missions ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def set_state(key: str, value: dict):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        con.execute(
            """
            INSERT INTO system_state(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(value, ensure_ascii=False), now),
        )


def get_state(key: str, default=None):
    # Defensive migration guard: older databases may predate system_state.
    init_db()
    with connect() as con:
        row = con.execute(
            "SELECT value_json, updated_at FROM system_state WHERE key = ?",
            (key,),
        ).fetchone()

    if not row:
        return default

    try:
        value = json.loads(row["value_json"])
    except Exception:
        value = default

    if isinstance(value, dict):
        value = dict(value)
        value["_updated_at"] = row["updated_at"]

    return value


def expire_commands(con):
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat()
    comments_cutoff = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
    rows = con.execute("SELECT id,type FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED') AND ((type IN ('READ_COMMENTS_SAMPLE','DISCOVER_MORE_RESULTS') AND COALESCE(ready_at,created_at) < ?) OR (type NOT IN ('READ_COMMENTS_SAMPLE','DISCOVER_MORE_RESULTS') AND COALESCE(ready_at,created_at) < ?))", (comments_cutoff,cutoff)).fetchall()
    for row in rows:
        if row['type']=='DISCOVER_MORE_RESULTS':
            con.execute("UPDATE discovery_sessions SET status='FINISHED',stop_reason='timeout',finished_at=? WHERE command_id=? AND status NOT IN ('FINISHED','FAILED','CANCELLED')",(datetime.now(timezone.utc).isoformat(),row['id']))
        now = datetime.now(timezone.utc).isoformat()
        con.execute("UPDATE bridge_commands SET status='EXPIRED', updated_at=?, detail='Command timed out' WHERE id=?", (now, row['id']))
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='safe_collection_batches'").fetchone():
            con.execute("UPDATE safe_collection_batches SET status='FAILED',stop_reason='COMMAND_TIMED_OUT_NO_RETRY',completed_at=? WHERE command_id=? AND status='PENDING'",(now,row['id']))
        con.execute("INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)", (now, 'WARN', 'command', f"{row['type']} #{row['id']} EXPIRED"))


def enqueue_search(query, extension_id):
    return enqueue_command('SEARCH', query, extension_id)


def enqueue_command(command_type, query, extension_id, options=None):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        if maintenance_active(con):
            from fastapi import HTTPException
            raise HTTPException(409, 'Development maintenance in progress')
        expire_commands(con)
        from .safe_collection import state as safe_state
        from . import collection_mode
        if command_type in collection_mode.DIRECT_TYPES:collection_mode.assert_allowed(con)
        from . import selective_enrichment as selective
        selected_run=selective.active(con)
        selected_permit=bool(selected_run and selective.CONTEXT.get() and selective.permitted(con,selected_run,command_type,query,options))
        if selected_run and not selected_permit:
            from fastapi import HTTPException
            raise HTTPException(409,'Selective pilot owns the tab; only its frozen IDs and current step are allowed')
        if selected_permit:options={**(options or {}),'selective_run_id':selected_run['id'],'selective_video_id':selected_run['current_video']}
        from .target_safety import blocked
        if command_type in ('READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE') and (blocked(con,query) or blocked(con,(options or {}).get('video_url',''))):
            from fastapi import HTTPException
            raise HTTPException(409,'TARGET_PREVIOUSLY_BLOCKED')
        if safe_state(con,'target_security_pending').get('items'):
            from fastapi import HTTPException
            raise HTTPException(409,'Target HTTP 403: waiting for passive healthy home/search')
        if safe_state(con,'safe_collection_guard').get('enabled') and not selected_permit:
            from fastapi import HTTPException
            raise HTTPException(409,'Safe recovery guard: only explicitly bounded collection is allowed')
        existing = con.execute("SELECT id,status FROM bridge_commands WHERE type=? AND query=? AND extension_id=? AND options_json=? AND status IN ('PENDING','DISPATCHED')", (command_type,query,extension_id,json.dumps(options or {}))).fetchone()
        if existing and command_type not in ('READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE'):
            return existing['id']
        if command_type in ('READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE','DISCOVER_MORE_RESULTS'):
            expire_commands(con)
            if con.execute("SELECT 1 FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED')").fetchone():
                from fastapi import HTTPException
                raise HTTPException(409,'Wait for the active command before starting this read')
        initial = 'PENDING'
        cur = con.execute("INSERT INTO bridge_commands(created_at,updated_at,type,query,status,extension_id,options_json,ready_at) VALUES (?,?,?,?,?,?,?,?)", (now, now, command_type, query, initial, extension_id,json.dumps(options or {}),None))
        command_id = cur.lastrowid
        if command_type=='DISCOVER_MORE_RESULTS':
            from .discovery import create_session
            create_session(con,command_id,query,options)
    log_event('command', f'{command_type} #{command_id} {initial}: {query}')
    if command_type == 'READ_SEARCH_RESULTS':
        log_event('capture', f'Capture requested #{command_id}: {query}')
    if command_type == 'READ_VIDEO_DETAIL':
        log_event('detail', f'Read-only video detail requested #{command_id}: {query}')
    if command_type == 'READ_COMMENTS_SAMPLE':
        log_event('comments', f'Comments sampling requested #{command_id}: target {(options or {}).get("target_count",30)}; READ ONLY')
    if command_type == 'READ_CREATOR_PROFILE':
        log_event('creator', f'Creator profile requested #{command_id}: {query}; READ ONLY')
    return command_id


def maintenance_active(con=None):
    if con is None:
        with connect() as connection:
            return maintenance_active(connection)
    row = con.execute("SELECT value_json FROM system_state WHERE key='dev_maintenance'").fetchone()
    if not row:
        return False
    value = json.loads(row[0])
    return bool(value.get('enabled') and value.get('expires_at', '') > datetime.now(timezone.utc).isoformat())


def list_commands():
    with connect() as con:
        expire_commands(con)
        return [dict(r) for r in con.execute('SELECT * FROM bridge_commands ORDER BY id DESC LIMIT 30').fetchall()]


def claim_command(extension_id):
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        expire_commands(con)
        from .target_safety import blocked
        from .safe_collection import state as target_state
        from .collection_mode import direct
        if direct(con)['status']=='PAUSED':
            con.execute("UPDATE bridge_commands SET status='FAILED',detail='DIRECT_VIDEO_ENRICHMENT_PAUSED',updated_at=? WHERE type IN ('READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE') AND status='PENDING'",(datetime.now(timezone.utc).isoformat(),))
        if target_state(con,'target_security_pending').get('items'):return None
        for candidate in con.execute("SELECT id,type,query,options_json FROM bridge_commands WHERE status='PENDING'").fetchall():
            if candidate['type'] in ('READ_VIDEO_DETAIL','READ_COMMENTS_SAMPLE','READ_CREATOR_PROFILE') and (blocked(con,candidate['query']) or blocked(con,json.loads(candidate['options_json']).get('video_url',''))):
                con.execute("UPDATE bridge_commands SET status='FAILED',detail='TARGET_PREVIOUSLY_BLOCKED',updated_at=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),candidate['id']))
        safety=con.execute("SELECT value_json FROM system_state WHERE key='browser_security_stop'").fetchone()
        if safety and json.loads(safety[0]).get('reason'):
            return None
        if con.execute("SELECT 1 FROM bridge_commands WHERE status='DISPATCHED'").fetchone():
            return None
        # Existing pending commands drain before development maintenance.
        statuses = "('PENDING')"
        row = con.execute(f"SELECT * FROM bridge_commands WHERE status IN {statuses} AND extension_id=? ORDER BY id LIMIT 1", (extension_id,)).fetchone()
        if not row:
            return None
        from .discovery_runner import DiscoveryRunner
        if not DiscoveryRunner.command_allowed(con,row):return None
        con.execute("UPDATE bridge_commands SET status='DISPATCHED', updated_at=?, ready_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), row['id']))
        if row['type']=='DISCOVER_MORE_RESULTS':
            con.execute("UPDATE discovery_sessions SET status='RUNNING',started_at=COALESCE(started_at,?) WHERE command_id=?",(datetime.now(timezone.utc).isoformat(),row['id']))
        result = dict(row)
        result['status'] = 'DISPATCHED'
    log_event('command', f"{row['type']} #{row['id']} DISPATCHED to Chrome")
    if row['type'] == 'READ_SEARCH_RESULTS':
        log_event('capture', f"Reading visible search results #{row['id']}")
    return result


def finish_command(command_id, extension_id, status, detail, capture=None, video_detail=None, comments_sample=None, creator_profile=None,search_diagnostics=None):
    evidence = creator_profile if creator_profile is not None else video_detail if video_detail is not None else capture if capture is not None else comments_sample
    result_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode()).hexdigest() if evidence is not None else ''
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        expire_commands(con)
        row = con.execute('SELECT * FROM bridge_commands WHERE id=? AND extension_id=?', (command_id, extension_id)).fetchone()
        if not row:
            return 'missing'
        if search_diagnostics is not None:
            options=json.loads(row['options_json'])
            if row['type']!='READ_SEARCH_RESULTS' or not (options.get('safe_collection_id') or options.get('mission_contract_id')) or search_diagnostics.get('query')!=row['query'] or len(json.dumps(search_diagnostics))>32768:return 'conflict'
            con.execute('INSERT OR IGNORE INTO safe_search_diagnostics VALUES (?,?,?)',(command_id,json.dumps(search_diagnostics),datetime.now(timezone.utc).isoformat()))
        if row['status'] == status and row['detail'] == detail and row['result_hash'] == result_hash:
            return 'ok'
        if row['status'] != 'DISPATCHED':
            return 'conflict'
        if row['type']=='DISCOVER_MORE_RESULTS':
            if evidence is not None or status=='SUCCEEDED':
                return 'conflict'
            from .discovery import session_for,finish
            finish(con,session_for(con,command_id),'error')
        if creator_profile is not None and status!='SUCCEEDED':
            return 'conflict'
        if creator_profile is not None and (row['type']!='READ_CREATOR_PROFILE' or any(value is not None for value in (capture,video_detail,comments_sample))):
            return 'conflict'
        if row['type']=='READ_CREATOR_PROFILE' and status=='SUCCEEDED':
            options=json.loads(row['options_json'])
            if creator_profile is None or creator_profile['profile_url']!=row['query']:
                return 'conflict'
            if not save_profile(con,creator_profile,command_id,datetime.now(timezone.utc).isoformat(),options['video_url']):
                return 'conflict'
        if comments_sample is not None and (row['type']!='READ_COMMENTS_SAMPLE' or capture is not None or video_detail is not None):
            return 'conflict'
        if row['type']=='READ_COMMENTS_SAMPLE' and status=='SUCCEEDED':
            from .extraction import video_identity
            if comments_sample is None or video_identity(comments_sample['video_url'])[1]!=video_identity(row['query'])[1] or comments_sample['target_count']!=json.loads(row['options_json']).get('target_count',30):
                return 'conflict'
            if not save_sample(con,comments_sample,command_id,datetime.now(timezone.utc).isoformat()):
                return 'conflict'
        if row['type'] == 'READ_VIDEO_DETAIL' and status == 'SUCCEEDED':
            from .extraction import video_identity
            if capture is not None or video_detail is None or video_identity(video_detail['video_url'])[1] != video_identity(row['query'])[1]:
                return 'conflict'
            if not save_detail(con, video_detail, command_id, datetime.now(timezone.utc).isoformat()):
                return 'conflict'
        elif video_detail is not None:
            return 'conflict'
        if row['type'] == 'READ_SEARCH_RESULTS' and status == 'SUCCEEDED':
            if capture is None or capture['query'] != row['query']:
                return 'conflict'
            options=json.loads(row['options_json'])
            if options.get('safe_collection_id') or options.get('mission_contract_id'):
                from .safe_collection import state as safe_state
                from .discovery_runner import DiscoveryRunner
                if safe_state(con,'browser_security_stop').get('reason') or not DiscoveryRunner.command_allowed(con,row) or len(capture['results'])>options['max_results'] or capture['links_detected']>options['max_results']:
                    return 'conflict'
            inserted, updated = store_observations(con, capture, f'command:{command_id}')
            now = datetime.now(timezone.utc).isoformat()
            for message in (f"{capture['links_detected']} result links detected",
                            f'{inserted} unique observations stored',
                            f'{updated} duplicates updated', 'Capture completed'):
                con.execute('INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)',
                            (now, 'INFO', 'capture', f'#{command_id} {message}'))
        elif capture is not None:
            return 'conflict'
        options=json.loads(row['options_json'])
        if options.get('safe_collection_id'):
            if status=='SUCCEEDED':
                from .discovery_runner import DiscoveryRunner
                DiscoveryRunner.post_capture(con,command_id)
            from .discovery_runner import DiscoveryRunner
            DiscoveryRunner.finish(con,row,status,capture,inserted if status=='SUCCEEDED' else 0,updated if status=='SUCCEEDED' else 0)
        elif options.get('mission_contract_id'):
            from .viral_products_mission import post_capture,finish
            if status=='SUCCEEDED':post_capture(con,command_id)
            finish(con,row,status,capture,inserted if status=='SUCCEEDED' else 0,updated if status=='SUCCEEDED' else 0)
        con.execute('UPDATE bridge_commands SET status=?, detail=?, updated_at=?, result_hash=? WHERE id=?', (status, detail, datetime.now(timezone.utc).isoformat(), result_hash, command_id))
    log_event('command', f"{row['type']} #{command_id} {status}: {detail}", 'ERROR' if status == 'FAILED' else 'INFO')
    return 'ok'


def store_observations(con, capture, capture_id):
    now = datetime.now(timezone.utc).isoformat()
    return save_capture(con, capture, capture_id, now)


def recent_videos(limit=20):
    with connect() as con:
        return recent(con, limit)


def extraction_quality():
    with connect() as con:
        return quality(con)


def known_video_url(url):
    from .extraction import video_identity
    _, strong_id = video_identity(url)
    with connect() as con:
        row = con.execute('SELECT canonical_url FROM videos WHERE source=? AND video_id=?', ('tiktok', strong_id)).fetchone()
    return row['canonical_url'] if row else None
