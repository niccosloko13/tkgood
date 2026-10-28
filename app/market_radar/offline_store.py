"""Isolated PostgreSQL storage for authorized offline product imports.

This module never writes to official market_radar_products or snapshots.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .models import MarketplaceProductObservation


class MarketImportStore:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connection(self):
        return psycopg.connect(self.database_url)

    def migrate(self) -> None:
        with self._connection() as con, con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS market_radar_offline_imports (
                    id UUID PRIMARY KEY,
                    marketplace TEXT NOT NULL CHECK (marketplace IN ('SHOPEE','ALIEXPRESS')),
                    imported_at TIMESTAMPTZ NOT NULL,
                    product_count INTEGER NOT NULL CHECK (product_count BETWEEN 0 AND 20),
                    source_kind TEXT NOT NULL CHECK (source_kind IN ('IMPORTED_FILE','FIXTURE'))
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS market_radar_offline_import_products (
                    batch_id UUID NOT NULL REFERENCES market_radar_offline_imports(id) ON DELETE CASCADE,
                    marketplace TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    source_category TEXT,
                    title TEXT NOT NULL,
                    price NUMERIC,
                    currency TEXT,
                    image_url TEXT,
                    product_url TEXT,
                    observed_at TIMESTAMPTZ NOT NULL,
                    evidence_json JSONB NOT NULL,
                    PRIMARY KEY (batch_id, marketplace, external_id)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS market_radar_offline_import_time_idx ON market_radar_offline_imports(imported_at DESC)")

    def save(self, observations: list[MarketplaceProductObservation], *, source_kind: str) -> str:
        if source_kind not in {"IMPORTED_FILE", "FIXTURE"} or len(observations) > 20:
            raise ValueError("Invalid import batch")
        if any(item.product.marketplace.value not in {"SHOPEE", "ALIEXPRESS"} for item in observations):
            raise ValueError("Only Shopee and AliExpress offline imports are accepted")
        if len({(item.product.marketplace.value, item.product.external_id) for item in observations}) != len(observations):
            raise ValueError("Duplicate product in import batch")
        batch_id = str(uuid.uuid4())
        self.migrate()
        with self._connection() as con, con.cursor() as cur:
            cur.execute(
                "INSERT INTO market_radar_offline_imports (id,marketplace,imported_at,product_count,source_kind) VALUES (%s,%s,%s,%s,%s)",
                (batch_id, observations[0].product.marketplace.value if observations else "SHOPEE",
                 datetime.now(timezone.utc), len(observations), source_kind),
            )
            for observation in observations:
                p = observation.product
                evidence = dict(observation.evidence)
                evidence.update({"import_origin": source_kind, "not_live": True, "ranking_available": False})
                cur.execute("""
                    INSERT INTO market_radar_offline_import_products
                    (batch_id,marketplace,external_id,source_category,title,price,currency,
                     image_url,product_url,observed_at,evidence_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                """, (batch_id,p.marketplace.value,p.external_id,p.source_category,p.title,observation.price,
                      observation.currency,p.image_url,p.product_url,observation.observed_at,
                      json.dumps(evidence,ensure_ascii=False)))
        return batch_id

    def latest(self, *, marketplace: str, limit: int = 20) -> dict[str, Any]:
        if marketplace not in {"SHOPEE", "ALIEXPRESS"}:
            raise ValueError("Unsupported marketplace")
        self.migrate()
        with self._connection() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT p.external_id,p.title,p.source_category,p.price,p.currency,p.image_url,
                       p.product_url,p.observed_at,b.imported_at,b.source_kind
                FROM market_radar_offline_import_products p
                JOIN market_radar_offline_imports b ON b.id=p.batch_id
                WHERE p.marketplace=%s
                ORDER BY b.imported_at DESC,p.external_id
                LIMIT %s
            """, (marketplace, min(max(limit,1),20)))
            rows = cur.fetchall()
        products = [
            {**row,
             "observed_at": row["observed_at"].isoformat(),
             "imported_at": row["imported_at"].isoformat(),
             "rank": None, "sales_count": None, "views": None,
             "not_live": True, "source_type": "IMPORTED_FILE"}
            for row in rows
        ]
        return {"marketplace": marketplace, "mode": "OFFLINE_IMPORT", "products": products,
                "official_ranking": False, "count": len(products)}
