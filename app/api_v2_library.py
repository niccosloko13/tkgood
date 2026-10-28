"""Paginated, read-only library adapter for UI V2."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .api_v2 import _friendly_name, _presentation_quality, _table_exists
from .db import connect

router = APIRouter(prefix="/api/v2")


def _metrics(fields: dict[str, Any]) -> dict[str, Any]:
    return {"views": fields.get("views"), "likes": fields.get("likes"), "comments": fields.get("comments_count"), "shares": fields.get("shares"), "favorites": fields.get("favorites")}


def _item(row) -> dict[str, Any]:
    data = dict(row)
    try:
        fields = json.loads(data.get("fields_json") or "{}")
    except (TypeError, ValueError):
        fields = {}
    metrics = _metrics(fields)
    product_name = data.get("product_name")
    return {
        "video_id": data.get("video_id") or str(data["id"]), "video_url": data.get("canonical_url"), "thumbnail_url": data.get("thumbnail_url"),
        "creator": data.get("creator_username") or data.get("creator_display_name"), "caption": data.get("caption"),
        "product": {"id": str(data["product_id"]) if data.get("product_id") is not None else None, "name": _friendly_name(product_name) if product_name else None},
        "metrics": metrics, "query": data.get("search_query"), "first_seen_at": data.get("first_seen_at"), "last_seen_at": data.get("last_seen_at"),
        "data_quality": _presentation_quality(data, {key: value for key, value in metrics.items() if value is not None}),
    }


def _base_sql(con) -> str:
    """Return the smallest compatible projection for an existing database.

    The V2 layer is deliberately a reader: older/empty databases can lack the
    candidate tables, so an absent product relationship must remain empty rather
    than make the Library unavailable.
    """
    products = "NULL AS product_id, NULL AS product_name"
    if _table_exists(con, "product_candidate_evidence") and _table_exists(con, "product_candidates"):
        products = """
          (SELECT c.id FROM product_candidate_evidence e JOIN product_candidates c ON c.id=e.candidate_id
             WHERE e.video_id=v.id ORDER BY e.observed_at DESC,c.id DESC LIMIT 1) AS product_id,
          (SELECT c.canonical_name FROM product_candidate_evidence e JOIN product_candidates c ON c.id=e.candidate_id
             WHERE e.video_id=v.id ORDER BY e.observed_at DESC,c.id DESC LIMIT 1) AS product_name
        """
    return f"""
      WITH latest AS (
        SELECT o.* FROM search_observations o
        WHERE o.id=(SELECT x.id FROM search_observations x WHERE x.video_id=o.video_id
                    ORDER BY x.observed_at DESC,x.id DESC LIMIT 1)
      )
      SELECT v.*, latest.search_query, latest.fields_json, {products}
      FROM videos v LEFT JOIN latest ON latest.video_id=v.id
    """


def library_read_model(con, page: int = 1, page_size: int = 25, text: str | None = None, quality: str | None = None,
                       identified: bool | None = None, query: str | None = None, creator: str | None = None,
                       sort: str = "recent", candidate_id: str | None = None) -> dict[str, Any]:
    if not _table_exists(con, "videos"):
        return {"page": page, "page_size": page_size, "total": 0, "items": [], "filters": {"queries": [], "creators": []}}
    source_rows = [_item(row) for row in con.execute(_base_sql(con)).fetchall()]
    rows = list(source_rows)
    needle = (text or "").casefold().strip()
    if needle:
        rows = [row for row in rows if needle in " ".join(str(value or "") for value in (row["caption"], row["creator"], row["product"]["name"], row["query"])).casefold()]
    if quality in {"COMPLETE", "PARTIAL", "MINIMAL"}:
        rows = [row for row in rows if row["data_quality"] == quality]
    if identified is True:
        rows = [row for row in rows if row["product"]["id"]]
    if candidate_id:
        rows = [row for row in rows if row["product"]["id"] == str(candidate_id)]
    if query:
        rows = [row for row in rows if row["query"] == query]
    if creator:
        rows = [row for row in rows if row["creator"] == creator]
    if sort == "oldest": rows.sort(key=lambda row: (row["first_seen_at"] or "", row["video_id"]))
    elif sort == "views": rows.sort(key=lambda row: (row["metrics"]["views"] is not None, row["metrics"]["views"] or 0), reverse=True)
    elif sort == "complete": rows.sort(key=lambda row: ({"COMPLETE": 2, "PARTIAL": 1, "MINIMAL": 0}[row["data_quality"]], row["last_seen_at"] or ""), reverse=True)
    else: rows.sort(key=lambda row: (row["last_seen_at"] or "", row["video_id"]), reverse=True)
    total = len(rows); start = (page - 1) * page_size
    options = source_rows
    return {"page": page, "page_size": page_size, "total": total, "items": rows[start:start + page_size],
            "filters": {"queries": sorted({row["query"] for row in options if row["query"]})[:50], "creators": sorted({row["creator"] for row in options if row["creator"]})[:50]}}


@router.get("/library")
def library(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=50), text: str | None = None,
            quality: str | None = None, identified: bool | None = None, query: str | None = None,
            creator: str | None = None, sort: str = "recent", candidate_id: str | None = None):
    if sort not in {"recent", "oldest", "views", "complete"}:
        raise HTTPException(422, "Ordenação inválida")
    import os
    if os.environ.get('VERCEL') and os.environ.get('OAUTH_DATABASE_URL') and os.environ.get('BABI_TIKTOK_NEON_READS') == '1':
        from .tiktok_neon_mirror import read_library
        return read_library(page=page, page_size=page_size, text=text, quality=quality,
                            identified=identified, query=query, creator=creator, sort=sort, candidate_id=candidate_id)
    with connect() as con:
        return library_read_model(con, page, page_size, text, quality, identified, query, creator, sort, candidate_id)


@router.get("/library/{video_id}")
def library_detail(video_id: str):
    import os
    if os.environ.get("VERCEL") and os.environ.get("OAUTH_DATABASE_URL") and os.environ.get("BABI_TIKTOK_NEON_READS") == "1":
        from .tiktok_neon_mirror import read_library
        # Mirror is a dedicated view; it does not contain historical
        # appearances until a subsequent audited migration.
        from .tiktok_neon_mirror import read_video
        item = read_video(video_id)
        if not item:
            raise HTTPException(404, "Conteúdo não encontrado")
        return {**item, "appearances": [],
                "technical": {"video_id": item["video_id"], "data_quality": item["data_quality"],
                              "history_status": "MIRROR_ONLY"}}
    with connect() as con:
        item = next((_item(row) for row in con.execute(_base_sql(con)).fetchall()
                     if str(row["video_id"] or row["id"]) == str(video_id)), None)
        if not item:
            raise HTTPException(404, "Conteúdo não encontrado")
        appearances = [dict(row) for row in con.execute("SELECT search_query,observed_at,search_position FROM search_observations WHERE video_id=(SELECT id FROM videos WHERE video_id=? OR id=? LIMIT 1) ORDER BY observed_at DESC,id DESC LIMIT 20", (video_id, video_id)).fetchall()]
        return {**item, "appearances": appearances,
                "technical": {"video_id": item["video_id"], "data_quality": item["data_quality"]}}
