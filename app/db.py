import json
import sqlite3
import hashlib
from datetime import datetime, timezone

from .config import DB_PATH


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


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
                type TEXT NOT NULL CHECK(type IN ('SEARCH','READ_SEARCH_RESULTS')),
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
        if 'READ_SEARCH_RESULTS' not in sql:
            con.execute("""CREATE TABLE bridge_commands_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, type TEXT NOT NULL CHECK(type IN ('SEARCH','READ_SEARCH_RESULTS')),
                query TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PENDING','DISPATCHED','SUCCEEDED','FAILED','EXPIRED')),
                extension_id TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '')""")
            con.execute('INSERT INTO bridge_commands_v2 SELECT * FROM bridge_commands')
            con.execute('DROP TABLE bridge_commands')
            con.execute('ALTER TABLE bridge_commands_v2 RENAME TO bridge_commands')
        if 'result_hash' not in {row['name'] for row in con.execute('PRAGMA table_info(bridge_commands)')}:
            con.execute("ALTER TABLE bridge_commands ADD COLUMN result_hash TEXT NOT NULL DEFAULT ''")


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
    rows = con.execute("SELECT id,type FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED') AND created_at < ?", (cutoff,)).fetchall()
    for row in rows:
        now = datetime.now(timezone.utc).isoformat()
        con.execute("UPDATE bridge_commands SET status='EXPIRED', updated_at=?, detail='Command timed out' WHERE id=?", (now, row['id']))
        con.execute("INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)", (now, 'WARN', 'command', f"{row['type']} #{row['id']} EXPIRED"))


def enqueue_search(query, extension_id):
    return enqueue_command('SEARCH', query, extension_id)


def enqueue_command(command_type, query, extension_id):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        cur = con.execute("INSERT INTO bridge_commands(created_at,updated_at,type,query,status,extension_id) VALUES (?,?,?,?,'PENDING',?)", (now, now, command_type, query, extension_id))
        command_id = cur.lastrowid
    log_event('command', f'{command_type} #{command_id} PENDING: {query}')
    if command_type == 'READ_SEARCH_RESULTS':
        log_event('capture', f'Capture requested #{command_id}: {query}')
    return command_id


def list_commands():
    with connect() as con:
        expire_commands(con)
        return [dict(r) for r in con.execute('SELECT * FROM bridge_commands ORDER BY id DESC LIMIT 30').fetchall()]


def claim_command(extension_id):
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        expire_commands(con)
        row = con.execute("SELECT * FROM bridge_commands WHERE status='PENDING' AND extension_id=? ORDER BY id LIMIT 1", (extension_id,)).fetchone()
        if not row:
            return None
        con.execute("UPDATE bridge_commands SET status='DISPATCHED', updated_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), row['id']))
        result = dict(row)
        result['status'] = 'DISPATCHED'
    log_event('command', f"{row['type']} #{row['id']} DISPATCHED to Chrome")
    if row['type'] == 'READ_SEARCH_RESULTS':
        log_event('capture', f"Reading visible search results #{row['id']}")
    return result


def finish_command(command_id, extension_id, status, detail, capture=None):
    result_hash = hashlib.sha256(json.dumps(capture, sort_keys=True, ensure_ascii=False).encode()).hexdigest() if capture is not None else ''
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        expire_commands(con)
        row = con.execute('SELECT * FROM bridge_commands WHERE id=? AND extension_id=?', (command_id, extension_id)).fetchone()
        if not row:
            return 'missing'
        if row['status'] == status and row['detail'] == detail and row['result_hash'] == result_hash:
            return 'ok'
        if row['status'] != 'DISPATCHED':
            return 'conflict'
        if row['type'] == 'READ_SEARCH_RESULTS' and status == 'SUCCEEDED':
            if capture is None or capture['query'] != row['query']:
                return 'conflict'
            inserted, updated = store_observations(con, capture)
            now = datetime.now(timezone.utc).isoformat()
            for message in (f"{capture['links_detected']} result links detected",
                            f'{inserted} unique observations stored',
                            f'{updated} duplicates updated', 'Capture completed'):
                con.execute('INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)',
                            (now, 'INFO', 'capture', f'#{command_id} {message}'))
        elif capture is not None:
            return 'conflict'
        con.execute('UPDATE bridge_commands SET status=?, detail=?, updated_at=?, result_hash=? WHERE id=?', (status, detail, datetime.now(timezone.utc).isoformat(), result_hash, command_id))
    log_event('command', f"{row['type']} #{command_id} {status}: {detail}", 'ERROR' if status == 'FAILED' else 'INFO')
    return 'ok'


def store_observations(con, capture):
    now = datetime.now(timezone.utc).isoformat()
    inserted = updated = 0
    for video in capture['results']:
        exists = con.execute('SELECT id FROM video_observations WHERE video_url=?', (video['video_url'],)).fetchone()
        fields = ('creator_username', 'creator_display_name', 'caption', 'views', 'likes', 'comments_count', 'shares', 'raw_visible_text', 'extraction_version')
        values = [video.get(field) for field in fields]
        if exists:
            con.execute('''UPDATE video_observations SET search_query=?, collected_at=?, last_seen_at=?,
                creator_username=?, creator_display_name=?, caption=?, views=?, likes=?, comments_count=?, shares=?,
                raw_visible_text=?, extraction_version=? WHERE id=?''', (capture['query'], now, now, *values, exists['id']))
            updated += 1
        else:
            con.execute('''INSERT INTO video_observations(search_query, video_url, collected_at, first_seen_at, last_seen_at,
                creator_username, creator_display_name, caption, views, likes, comments_count, shares, raw_visible_text, extraction_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (capture['query'], video['video_url'], now, now, now, *values))
            inserted += 1
    return inserted, updated


def recent_videos(limit=20):
    with connect() as con:
        total = con.execute('SELECT COUNT(*) FROM video_observations').fetchone()[0]
        items = [dict(row) for row in con.execute('SELECT * FROM video_observations ORDER BY last_seen_at DESC,id DESC LIMIT ?', (limit,))]
    return {'total': total, 'items': items}
