"""Explicit, manual local TikTok library synchronization to hosted Neon.

Needs BABI_TIKTOK_SYNC_TOKEN and BABI_TIKTOK_SYNC_URL (the Babi site URL).
Sends only sanitized library presentation data; never uploads SQLite files,
session material, cookies, bridge commands or browser profiles.
"""
from __future__ import annotations
import argparse
import os
import time
from urllib import request, error

from app.db import connect
from app.api_v2_library import library_read_model
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=2000)
    args = parser.parse_args()
    if not 1 <= args.limit <= 10000:
        parser.error("limit must be 1..10000")
    rows = []
    with connect() as con:
        page = 1
        while len(rows) < args.limit:
            response = library_read_model(con, page=page, page_size=100)
            if not response["items"]:
                break
            rows.extend(response["items"])
            if len(response["items"]) < 100:
                break
            page += 1
    rows = rows[:args.limit]
    print(f"Local TikTok library records prepared: {len(rows)}")
    if args.dry_run:
        print("Dry run: no network requests or changes.")
        return 0
    base = os.getenv("BABI_TIKTOK_SYNC_URL", "").rstrip("/")
    token = os.getenv("BABI_TIKTOK_SYNC_TOKEN", "")
    if not base.startswith("https://") or len(token) < 32:
        print("Set a protected HTTPS BABI_TIKTOK_SYNC_URL and BABI_TIKTOK_SYNC_TOKEN.")
        return 2
    if not rows:
        print("No local library records: nothing uploaded.")
        return 0
    for index in range(0, len(rows), 100):
        chunk = rows[index:index+100]
        payload = json.dumps({"videos": chunk}, ensure_ascii=False).encode("utf-8")
        req = request.Request(base + "/api/v2/tiktok-sync/videos", data=payload,
                              headers={"Content-Type": "application/json", "X-Babi-Tiktok-Sync": token},
                              method="POST")
        try:
            with request.urlopen(req, timeout=25) as response:
                if response.status != 200:
                    raise RuntimeError("Sync rejected")
        except (error.HTTPError, error.URLError, TimeoutError) as exc:
            print(f"Batch {index // 100 + 1} failed; no token details emitted: {type(exc).__name__}")
            return 2
        print(f"Uploaded {min(index+100,len(rows))}/{len(rows)} library records.")
        time.sleep(.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
