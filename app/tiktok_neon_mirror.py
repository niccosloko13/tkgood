"""Opt-in TikTok library mirror in Neon; never changes collector SQLite.

The local collector remains the writer. Only server-authenticated snapshots may
be upserted. No public uploads, no cookies, no browser state and no TikTok
engagement commands are accepted.
"""
from __future__ import annotations
import hmac
import os
from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/v2/tiktok-sync")

class PublicVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_:-]+$")
    video_url: str | None = Field(default=None, max_length=2048)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    creator: str | None = Field(default=None, max_length=256)
    caption: str | None = Field(default=None, max_length=5000)
    product: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    query: str | None = Field(default=None, max_length=256)
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    data_quality: str = Field(default="MINIMAL", pattern="^(MINIMAL|PARTIAL|COMPLETE)$")

class SyncBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    videos: list[PublicVideo] = Field(min_length=1, max_length=100)

def configured() -> bool:
    return bool(os.environ.get("OAUTH_DATABASE_URL"))

def _connect():
    return psycopg.connect(os.environ["OAUTH_DATABASE_URL"])

def _authorize(request: Request):
    secret = os.environ.get("BABI_TIKTOK_SYNC_TOKEN", "")
    supplied = request.headers.get("X-Babi-Tiktok-Sync", "")
    if len(secret) < 32:
        raise HTTPException(503, "TikTok synchronization is not configured")
    if not supplied or not hmac.compare_digest(secret, supplied):
        raise HTTPException(401, "TikTok sync authorization required")

def migrate():
    with _connect() as con, con.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS babi_tiktok_library_mirror (
                video_id TEXT PRIMARY KEY, payload JSONB NOT NULL,
                last_seen_at TEXT, synced_at TIMESTAMPTZ NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS babi_tiktok_mirror_synced_idx ON babi_tiktok_library_mirror(synced_at DESC)")

def _validate_public_video(video: PublicVideo) -> dict[str, Any]:
    data = video.model_dump()
    # Strictly allow presentation metrics. No secrets/cookies/raw browser HTML.
    data["metrics"] = {k: v for k, v in data["metrics"].items()
                       if k in {"views", "likes", "comments", "shares", "favorites"}
                       and isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 10**15}
    product = data["product"]
    data["product"] = {k: v for k, v in product.items() if k in {"id", "name"} and (v is None or isinstance(v, str)) and (v is None or len(v) <= 256)}
    return data

@router.post("/videos")
def push_videos(payload: SyncBatch, request: Request):
    _authorize(request)
    if not configured():
        raise HTTPException(503, "Hosted storage unavailable")
    import json
    migrate()
    timestamp = datetime.now(timezone.utc)
    with _connect() as con, con.cursor() as cur:
        for item in payload.videos:
            data = _validate_public_video(item)
            cur.execute("""
                INSERT INTO babi_tiktok_library_mirror(video_id,payload,last_seen_at,synced_at)
                VALUES(%s,%s::jsonb,%s,%s)
                ON CONFLICT(video_id) DO UPDATE SET
                payload=EXCLUDED.payload,last_seen_at=EXCLUDED.last_seen_at,
                synced_at=EXCLUDED.synced_at
            """, (item.video_id, json.dumps(data, ensure_ascii=False), item.last_seen_at, timestamp))
    return {"accepted": len(payload.videos), "synced_at": timestamp.isoformat()}

def read_library(*, page: int = 1, page_size: int = 25, text: str | None = None,
                 quality: str | None = None, identified: bool | None = None,
                 query: str | None = None, creator: str | None = None,
                 sort: str = "recent", candidate_id: str | None = None) -> dict:
    if not configured():
        return {"page": page, "page_size": page_size, "total": 0, "items": [],
                "filters": {"queries": [], "creators": []}, "storage": "NEON_NOT_CONFIGURED"}
    migrate()
    with _connect() as con, con.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT payload FROM babi_tiktok_library_mirror")
        rows = [row["payload"] for row in cur.fetchall()]
    needle = (text or "").casefold().strip()
    if needle:
        rows = [v for v in rows if needle in " ".join(str(v.get(k) or "") for k in ("caption", "creator", "query")).casefold()
                or needle in str((v.get("product") or {}).get("name") or "").casefold()]
    if quality: rows = [v for v in rows if v.get("data_quality") == quality]
    if identified: rows = [v for v in rows if (v.get("product") or {}).get("id")]
    if candidate_id: rows = [v for v in rows if str((v.get("product") or {}).get("id")) == candidate_id]
    if query: rows = [v for v in rows if v.get("query") == query]
    if creator: rows = [v for v in rows if v.get("creator") == creator]
    all_rows = list(rows)
    if sort == "oldest": rows.sort(key=lambda v: (v.get("first_seen_at") or "", v["video_id"]))
    elif sort == "views": rows.sort(key=lambda v: ((v.get("metrics") or {}).get("views") or 0), reverse=True)
    elif sort == "complete": rows.sort(key=lambda v: ({"COMPLETE":2,"PARTIAL":1,"MINIMAL":0}.get(v.get("data_quality"),0),v.get("last_seen_at") or ""),reverse=True)
    else: rows.sort(key=lambda v: (v.get("last_seen_at") or "",v["video_id"]),reverse=True)
    start = (page-1)*page_size
    return {"page":page,"page_size":page_size,"total":len(rows),
            "items":rows[start:start+page_size],
            "filters":{"queries":sorted({v["query"] for v in all_rows if v.get("query")})[:50],
                       "creators":sorted({v["creator"] for v in all_rows if v.get("creator")})[:50]},
            "storage":"NEON_MIRROR"}


def read_video(video_id: str) -> dict[str, Any] | None:
    if not configured():
        return None
    migrate()
    with _connect() as con, con.cursor() as cur:
        cur.execute("SELECT payload FROM babi_tiktok_library_mirror WHERE video_id=%s", (video_id,))
        row = cur.fetchone()
    return row[0] if row else None

@router.get("/status")
def status():
    if not configured():
        return {"enabled":False,"storage":"NOT_CONFIGURED","count":0,"last_synced_at":None}
    migrate()
    with _connect() as con, con.cursor() as cur:
        cur.execute("SELECT count(*), max(synced_at) FROM babi_tiktok_library_mirror")
        count, synced = cur.fetchone()
    return {"enabled":True,"storage":"NEON_MIRROR","count":count,"last_synced_at":synced.isoformat() if synced else None}
