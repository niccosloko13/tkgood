from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from .models import MarketplaceProductObservation, RunStatus


def migrate(con: sqlite3.Connection) -> None:
    con.executescript("""
      CREATE TABLE IF NOT EXISTS market_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, marketplace TEXT NOT NULL, external_id TEXT NOT NULL,
        title TEXT NOT NULL, normalized_title TEXT NOT NULL, brand TEXT, category TEXT, source_category TEXT,
        image_url TEXT, product_url TEXT, seller_name TEXT, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
        UNIQUE(marketplace, external_id)
      );
      CREATE TABLE IF NOT EXISTS market_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL REFERENCES market_products(id), observed_at TEXT NOT NULL,
        rank INTEGER, price REAL, currency TEXT, sales_count INTEGER, order_count INTEGER, views INTEGER,
        rating REAL, reviews INTEGER, stock INTEGER, source_type TEXT NOT NULL, source_confidence TEXT NOT NULL,
        source_window TEXT, product_url TEXT, evidence_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(product_id, observed_at)
      );
      CREATE TABLE IF NOT EXISTS market_runs (
        id TEXT PRIMARY KEY, marketplace TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
        category TEXT, requested_limit INTEGER NOT NULL, received_count INTEGER NOT NULL DEFAULT 0, error_message TEXT
      );
      CREATE TABLE IF NOT EXISTS market_search_trends (
        id INTEGER PRIMARY KEY AUTOINCREMENT, marketplace TEXT NOT NULL, keyword TEXT NOT NULL,
        trend_type TEXT NOT NULL, position INTEGER NOT NULL, category TEXT, url TEXT,
        observed_at TEXT NOT NULL, source_type TEXT NOT NULL, source_window TEXT,
        evidence_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(marketplace, keyword, trend_type, category, observed_at)
      );
      CREATE TABLE IF NOT EXISTS market_source_state (
        marketplace TEXT PRIMARY KEY, available INTEGER NOT NULL DEFAULT 0, last_success_at TEXT, last_error_at TEXT,
        last_error TEXT, capabilities_json TEXT NOT NULL DEFAULT '{}', source_type TEXT, source_confidence TEXT
      );
      CREATE INDEX IF NOT EXISTS market_products_lookup ON market_products(marketplace, external_id);
      CREATE INDEX IF NOT EXISTS market_snapshots_product_time ON market_snapshots(product_id, observed_at DESC);
      CREATE INDEX IF NOT EXISTS market_snapshots_observed ON market_snapshots(observed_at DESC);
      CREATE INDEX IF NOT EXISTS market_search_trends_lookup ON market_search_trends(marketplace, category, observed_at DESC);
    """)
    # The foundation initially only needed received_count. These additive columns
    # make partial official-API runs auditable without changing existing rows.
    existing = {row["name"] for row in con.execute("PRAGMA table_info(market_runs)")}
    for name in ("enriched_count", "partial_count", "failure_count"):
        if name not in existing:
            con.execute(f"ALTER TABLE market_runs ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_observation(con: sqlite3.Connection, observation: MarketplaceProductObservation) -> int:
    product = observation.product
    con.execute("""INSERT INTO market_products(marketplace,external_id,title,normalized_title,brand,category,source_category,image_url,product_url,seller_name,first_seen_at,last_seen_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(marketplace,external_id) DO UPDATE SET
      title=excluded.title,normalized_title=excluded.normalized_title,brand=excluded.brand,category=excluded.category,
      source_category=excluded.source_category,image_url=excluded.image_url,product_url=excluded.product_url,
      seller_name=excluded.seller_name,last_seen_at=excluded.last_seen_at""",
      (product.marketplace.value, product.external_id, product.title, product.normalized_title, product.brand,
       product.category.value if product.category else None, product.source_category, product.image_url, product.product_url,
       product.seller_name, observation.observed_at, observation.observed_at))
    row = con.execute("SELECT id FROM market_products WHERE marketplace=? AND external_id=?", (product.marketplace.value, product.external_id)).fetchone()
    product_id = int(row[0])
    con.execute("""INSERT INTO market_snapshots(product_id,observed_at,rank,price,currency,sales_count,order_count,views,rating,reviews,stock,source_type,source_confidence,source_window,product_url,evidence_json)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(product_id,observed_at) DO UPDATE SET
      rank=excluded.rank,price=excluded.price,currency=excluded.currency,sales_count=excluded.sales_count,order_count=excluded.order_count,
      views=excluded.views,rating=excluded.rating,reviews=excluded.reviews,stock=excluded.stock,source_type=excluded.source_type,
      source_confidence=excluded.source_confidence,source_window=excluded.source_window,product_url=excluded.product_url,evidence_json=excluded.evidence_json""",
      (product_id, observation.observed_at, observation.rank, observation.price, observation.currency, observation.sales_count,
       observation.order_count, observation.views, observation.rating, observation.reviews, observation.stock,
       observation.source_type.value, observation.source_confidence.value, observation.source_window, product.product_url,
       json.dumps(observation.evidence, ensure_ascii=False, sort_keys=True)))
    return product_id


def create_run(con: sqlite3.Connection, marketplace: str, category: str | None, requested_limit: int) -> str:
    ident = str(uuid.uuid4()); con.execute("INSERT INTO market_runs(id,marketplace,started_at,status,category,requested_limit) VALUES (?,?,?,?,?,?)", (ident, marketplace, _now(), RunStatus.PENDING.value, category, requested_limit)); return ident


def finish_run(con: sqlite3.Connection, ident: str, status: RunStatus, received_count: int = 0, error_message: str | None = None,
               *, enriched_count: int = 0, partial_count: int = 0, failure_count: int = 0) -> None:
    con.execute("""UPDATE market_runs SET finished_at=?,status=?,received_count=?,error_message=?,
      enriched_count=?,partial_count=?,failure_count=? WHERE id=?""",
      (_now(), status.value, received_count, error_message, enriched_count, partial_count, failure_count, ident))


def save_search_trends(con: sqlite3.Connection, trends: list[dict]) -> int:
    for trend in trends:
        con.execute("""INSERT INTO market_search_trends(marketplace,keyword,trend_type,position,category,url,observed_at,source_type,source_window,evidence_json)
          VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(marketplace,keyword,trend_type,category,observed_at) DO UPDATE SET
          position=excluded.position,url=excluded.url,evidence_json=excluded.evidence_json""",
          (trend["marketplace"], trend["keyword"], trend["trend_type"], trend["position"], trend.get("category"),
           trend.get("url"), trend["observed_at"], trend["source_type"], trend.get("source_window"),
           json.dumps(trend.get("evidence", {}), ensure_ascii=False, sort_keys=True)))
    return len(trends)


def search_trends(con: sqlite3.Connection, *, marketplace: str, category: str | None = None, limit: int = 50) -> list[dict]:
    where = ["marketplace=?"]; params: list[object] = [marketplace]
    if category:
        where.append("category=?"); params.append(category)
    rows = con.execute(f"""SELECT * FROM market_search_trends WHERE {' AND '.join(where)}
      AND id IN (SELECT max(id) FROM market_search_trends GROUP BY keyword,trend_type,category)
      ORDER BY trend_type,position LIMIT ?""", [*params, min(max(1, limit), 50)]).fetchall()
    return [dict(row) for row in rows]


def set_source_state(con: sqlite3.Connection, marketplace: str, *, available: bool, capabilities: dict, source_type: str | None, source_confidence: str | None, error: str | None = None) -> None:
    now = _now()
    con.execute("""INSERT INTO market_source_state(marketplace,available,last_success_at,last_error_at,last_error,capabilities_json,source_type,source_confidence)
      VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(marketplace) DO UPDATE SET available=excluded.available,
      last_success_at=CASE WHEN excluded.available THEN excluded.last_success_at ELSE market_source_state.last_success_at END,
      last_error_at=CASE WHEN excluded.last_error IS NOT NULL THEN excluded.last_error_at ELSE market_source_state.last_error_at END,
      last_error=excluded.last_error,capabilities_json=excluded.capabilities_json,source_type=excluded.source_type,source_confidence=excluded.source_confidence""",
      (marketplace, int(available), now if available else None, now if error else None, error, json.dumps(capabilities, sort_keys=True), source_type, source_confidence))


def history(con: sqlite3.Connection, *, marketplace: str, external_id: str | None = None, category: str | None = None, since: str | None = None) -> list[dict]:
    where = ["p.marketplace=?"]; params: list[object] = [marketplace]
    if external_id: where.append("p.external_id=?"); params.append(external_id)
    if category: where.append("p.category=?"); params.append(category)
    if since: where.append("s.observed_at>=?"); params.append(since)
    return [dict(row) for row in con.execute(f"SELECT p.*,s.* FROM market_products p JOIN market_snapshots s ON s.product_id=p.id WHERE {' AND '.join(where)} ORDER BY s.observed_at", params)]
