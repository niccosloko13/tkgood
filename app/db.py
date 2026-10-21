import json
import sqlite3
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
                type TEXT NOT NULL CHECK(type = 'SEARCH'),
                query TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING','DISPATCHED','SUCCEEDED','FAILED','EXPIRED')),
                extension_id TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT ''
            );
            """
        )


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
    rows = con.execute("SELECT id FROM bridge_commands WHERE status IN ('PENDING','DISPATCHED') AND created_at < ?", (cutoff,)).fetchall()
    for row in rows:
        now = datetime.now(timezone.utc).isoformat()
        con.execute("UPDATE bridge_commands SET status='EXPIRED', updated_at=?, detail='Command timed out' WHERE id=?", (now, row['id']))
        con.execute("INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)", (now, 'WARN', 'command', f"SEARCH #{row['id']} EXPIRED"))


def enqueue_search(query, extension_id):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        cur = con.execute("INSERT INTO bridge_commands(created_at,updated_at,type,query,status,extension_id) VALUES (?,?,'SEARCH',?,'PENDING',?)", (now, now, query, extension_id))
        command_id = cur.lastrowid
    log_event('command', f'SEARCH #{command_id} PENDING: {query}')
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
    log_event('command', f"SEARCH #{row['id']} DISPATCHED to Chrome")
    return result


def finish_command(command_id, extension_id, status, detail):
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        expire_commands(con)
        row = con.execute('SELECT * FROM bridge_commands WHERE id=? AND extension_id=?', (command_id, extension_id)).fetchone()
        if not row:
            return 'missing'
        if row['status'] == status and row['detail'] == detail:
            return 'ok'
        if row['status'] != 'DISPATCHED':
            return 'conflict'
        con.execute('UPDATE bridge_commands SET status=?, detail=?, updated_at=? WHERE id=?', (status, detail, datetime.now(timezone.utc).isoformat(), command_id))
    log_event('command', f'SEARCH #{command_id} {status}: {detail}', 'ERROR' if status == 'FAILED' else 'INFO')
    return 'ok'
