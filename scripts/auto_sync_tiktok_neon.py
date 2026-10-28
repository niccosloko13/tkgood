"""Persistent outbox for syncing the local TikTok library to Babi on Vercel.

Read-only against collector SQLite. No TikTok access, Chrome control or actions.
Only sends a bounded public-facing library projection over HTTPS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from urllib import error, request, parse

from app.api_v2_library import library_read_model
from app.db import connect

DEFAULT_OUTBOX = Path(__file__).resolve().parents[1] / "data" / "tiktok_neon_outbox.db"
MAX_BATCH = 50


def outbox(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS pending (
        video_id TEXT PRIMARY KEY, checksum TEXT NOT NULL,
        payload TEXT NOT NULL, updated_at INTEGER NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS delivered (
        video_id TEXT PRIMARY KEY, checksum TEXT NOT NULL
    )""")
    con.commit()
    return con


def public_projection(row: dict) -> dict:
    allowed = ("video_id", "video_url", "thumbnail_url", "creator", "caption", "product",
               "metrics", "query", "first_seen_at", "last_seen_at", "data_quality")
    return {key: row[key] for key in allowed if key in row}


def enqueue_from_library(con: sqlite3.Connection, *, limit: int = 10000) -> tuple[int, int]:
    added = scanned = 0
    with connect() as local:
        page = 1
        while scanned < limit:
            result = library_read_model(local, page=page, page_size=min(50, limit-scanned))
            rows = result["items"]
            if not rows:
                break
            for row in rows:
                item = public_projection(row)
                blob = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
                video_id = str(item["video_id"])
                delivered = con.execute("SELECT checksum FROM delivered WHERE video_id=?", (video_id,)).fetchone()
                pending = con.execute("SELECT checksum FROM pending WHERE video_id=?", (video_id,)).fetchone()
                if (delivered and delivered[0] == digest) or (pending and pending[0] == digest):
                    continue
                con.execute("""INSERT INTO pending(video_id,checksum,payload,updated_at,attempts)
                    VALUES (?,?,?,strftime('%s','now'),0)
                    ON CONFLICT(video_id) DO UPDATE SET checksum=excluded.checksum,
                    payload=excluded.payload,updated_at=excluded.updated_at,attempts=0""",
                    (video_id,digest,blob))
                added += 1
            scanned += len(rows)
            if len(rows) < 50:
                break
            page += 1
    con.commit()
    return scanned, added


def send_pending(con: sqlite3.Connection, *, base: str, secret: str) -> tuple[int,int]:
    rows = con.execute("SELECT video_id,checksum,payload FROM pending ORDER BY updated_at,video_id LIMIT ?", (MAX_BATCH,)).fetchall()
    if not rows:
        return 0, 0
    payload = {"videos": [json.loads(row[2]) for row in rows]}
    req = request.Request(
        base + "/api/v2/tiktok-sync/videos",
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type":"application/json","X-Babi-Tiktok-Sync":secret},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=25) as response:
            result = json.loads(response.read(2048))
            if response.status != 200 or result.get("accepted") != len(rows):
                raise ValueError("Invalid sync acknowledgement")
    except (error.HTTPError, error.URLError, TimeoutError, ValueError) as exc:
        con.executemany("UPDATE pending SET attempts=attempts+1 WHERE video_id=?", [(row[0],) for row in rows])
        con.commit()
        print(f"Sync request failed: {type(exc).__name__}", file=sys.stderr)
        return 0, len(rows)
    with con:
        for video_id, checksum, _ in rows:
            con.execute("INSERT INTO delivered(video_id,checksum) VALUES (?,?) ON CONFLICT(video_id) DO UPDATE SET checksum=excluded.checksum", (video_id, checksum))
            con.execute("DELETE FROM pending WHERE video_id=? AND checksum=?", (video_id, checksum))
    return len(rows), 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Sync one cycle then exit")
    parser.add_argument("--dry-run", action="store_true", help="Preview local work without sending")
    parser.add_argument("--interval", type=int, default=90)
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--outbox", type=Path, default=DEFAULT_OUTBOX)
    args = parser.parse_args()
    if not 30 <= args.interval <= 3600 or not 1 <= args.limit <= 10000:
        parser.error("interval must be 30..3600 seconds; limit must be 1..10000")
    base = os.getenv("BABI_TIKTOK_SYNC_URL", "").rstrip("/")
    secret = os.getenv("BABI_TIKTOK_SYNC_TOKEN", "")
    parsed = parse.urlparse(base)
    if not args.dry_run and (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.path or len(secret) < 32):
        print("Protected HTTPS BABI_TIKTOK_SYNC_URL and BABI_TIKTOK_SYNC_TOKEN are required.",file=sys.stderr)
        return 2
    db = outbox(args.outbox)
    try:
        while True:
            scanned, queued = enqueue_from_library(db, limit=args.limit)
            pending = db.execute("SELECT count(*) FROM pending").fetchone()[0]
            if args.dry_run:
                print(f"Local scan={scanned} newly_queued={queued} pending={pending}; no network sent")
                return 0
            sent, failed = send_pending(db, base=base, secret=secret)
            print(f"Scanned={scanned} queued={queued} delivered={sent} retry_pending={pending-sent} failed={failed}")
            if args.once:
                return 2 if failed else 0
            time.sleep(args.interval if not failed else max(args.interval, 120))
    except KeyboardInterrupt:
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
