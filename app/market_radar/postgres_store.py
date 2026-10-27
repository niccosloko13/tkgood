"""Small Postgres persistence adapter for hosted Market Radar collections."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import psycopg

from .adapters.mercado_livre import MercadoLivreCategoryNotRanked, MercadoLivreError
from .models import MarketplaceProductObservation


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PostgresMarketStore:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connect(self):
        return psycopg.connect(self.database_url)

    def migrate(self) -> None:
        with self._connect() as con, con.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS market_radar_products (id BIGSERIAL PRIMARY KEY, marketplace TEXT NOT NULL, external_id TEXT NOT NULL, title TEXT NOT NULL, normalized_title TEXT NOT NULL, source_category TEXT, image_url TEXT, product_url TEXT, seller_name TEXT, first_seen_at TIMESTAMPTZ NOT NULL, last_seen_at TIMESTAMPTZ NOT NULL, UNIQUE(marketplace,external_id))")
            cur.execute("CREATE TABLE IF NOT EXISTS market_radar_snapshots (id BIGSERIAL PRIMARY KEY, product_id BIGINT NOT NULL REFERENCES market_radar_products(id), observed_at TIMESTAMPTZ NOT NULL, rank INTEGER, price NUMERIC, currency TEXT, source_type TEXT NOT NULL, source_confidence TEXT NOT NULL, source_window TEXT, product_url TEXT, evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb, UNIQUE(product_id,observed_at))")
            cur.execute("CREATE TABLE IF NOT EXISTS market_radar_runs (id UUID PRIMARY KEY, marketplace TEXT NOT NULL, category TEXT, started_at TIMESTAMPTZ NOT NULL, finished_at TIMESTAMPTZ, status TEXT NOT NULL, requested_limit INTEGER NOT NULL, received_count INTEGER NOT NULL DEFAULT 0, enriched_count INTEGER NOT NULL DEFAULT 0, partial_count INTEGER NOT NULL DEFAULT 0, failure_count INTEGER NOT NULL DEFAULT 0, error_code TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS market_radar_trends (id BIGSERIAL PRIMARY KEY, marketplace TEXT NOT NULL, keyword TEXT NOT NULL, trend_type TEXT NOT NULL, position INTEGER NOT NULL, category TEXT, url TEXT, observed_at TIMESTAMPTZ NOT NULL, source_type TEXT NOT NULL, source_window TEXT, evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb, UNIQUE(marketplace,keyword,trend_type,category,observed_at))")
            cur.execute("CREATE INDEX IF NOT EXISTS market_radar_snapshot_time_idx ON market_radar_snapshots(observed_at DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS market_radar_trend_time_idx ON market_radar_trends(marketplace,category,observed_at DESC)")

    def _save_observation(self, cur, item: MarketplaceProductObservation) -> None:
        p = item.product
        cur.execute("""INSERT INTO market_radar_products(marketplace,external_id,title,normalized_title,source_category,image_url,product_url,seller_name,first_seen_at,last_seen_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(marketplace,external_id) DO UPDATE SET title=EXCLUDED.title,normalized_title=EXCLUDED.normalized_title,source_category=EXCLUDED.source_category,image_url=EXCLUDED.image_url,product_url=EXCLUDED.product_url,seller_name=EXCLUDED.seller_name,last_seen_at=EXCLUDED.last_seen_at RETURNING id""",
            (p.marketplace.value,p.external_id,p.title,p.normalized_title,p.source_category,p.image_url,p.product_url,p.seller_name,item.observed_at,item.observed_at))
        product_id = cur.fetchone()[0]
        cur.execute("""INSERT INTO market_radar_snapshots(product_id,observed_at,rank,price,currency,source_type,source_confidence,source_window,product_url,evidence_json)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT(product_id,observed_at) DO UPDATE SET rank=EXCLUDED.rank,price=EXCLUDED.price,currency=EXCLUDED.currency,evidence_json=EXCLUDED.evidence_json""",
            (product_id,item.observed_at,item.rank,item.price,item.currency,item.source_type.value,item.source_confidence.value,item.source_window,p.product_url,json.dumps(item.evidence,ensure_ascii=False)))

    def collect(self, adapter, *, category: str, limit: int = 20, collect_trends: bool = True) -> dict:
        self.migrate(); run_id = str(uuid.uuid4()); started = _now(); limit = min(max(1,limit),20)
        with self._connect() as con, con.cursor() as cur:
            cur.execute("INSERT INTO market_radar_runs(id,marketplace,category,started_at,status,requested_limit) VALUES(%s,%s,%s,%s,'RUNNING',%s)", (run_id,adapter.marketplace.value,category,started,limit))
        try:
            category_info = adapter.category_info(category)
            if not category_info.get("is_leaf"):
                raise MercadoLivreCategoryNotRanked("Best-seller rankings require a leaf category")
            observations = adapter.fetch_top_products(category=category, limit=limit)
            trends = adapter.fetch_trends(category=category) if collect_trends else []
            partial = sum(1 for item in observations if not item.evidence.get("detail_resolved", True))
            with self._connect() as con, con.cursor() as cur:
                for item in observations:
                    self._save_observation(cur, item)
                for trend in trends:
                    cur.execute("""INSERT INTO market_radar_trends(marketplace,keyword,trend_type,position,category,url,observed_at,source_type,source_window,evidence_json)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT(marketplace,keyword,trend_type,category,observed_at) DO UPDATE SET position=EXCLUDED.position,url=EXCLUDED.url,evidence_json=EXCLUDED.evidence_json""",
                        (trend["marketplace"],trend["keyword"],trend["trend_type"],trend["position"],trend.get("category"),trend.get("url"),trend["observed_at"],trend["source_type"],trend.get("source_window"),json.dumps(trend.get("evidence",{}),ensure_ascii=False)))
                status = "PARTIAL" if partial else "COMPLETED"
                cur.execute("UPDATE market_radar_runs SET finished_at=%s,status=%s,received_count=%s,enriched_count=%s,partial_count=%s,failure_count=%s WHERE id=%s", (_now(),status,len(observations),len(observations)-partial,partial,partial,run_id))
            return {"id":run_id,"status":status,"category":category,"category_name":category_info.get("name"),"received_count":len(observations),"enriched_count":len(observations)-partial,"partial_count":partial,"failure_count":partial,"trend_count":len(trends)}
        except MercadoLivreCategoryNotRanked:
            with self._connect() as con, con.cursor() as cur:
                cur.execute("UPDATE market_radar_runs SET finished_at=%s,status='PARTIAL',failure_count=1,error_code='CATEGORY_NOT_RANKED' WHERE id=%s",(_now(),run_id))
            return {"id":run_id,"status":"PARTIAL","category":category,"received_count":0,"partial_count":0,"failure_count":1,"error":"CATEGORY_NOT_RANKED"}
        except MercadoLivreError:
            with self._connect() as con, con.cursor() as cur:
                cur.execute("UPDATE market_radar_runs SET finished_at=%s,status='FAILED',failure_count=1,error_code='EXTERNAL_FAILURE' WHERE id=%s",(_now(),run_id))
            return {"id":run_id,"status":"FAILED","category":category,"received_count":0,"partial_count":0,"failure_count":1,"error":"EXTERNAL_FAILURE"}

    def top(self, category: str | None = None, limit: int = 20) -> dict:
        self.migrate(); limit=min(max(1,limit),20)
        clause="WHERE p.marketplace='MERCADO_LIVRE'"; params=[]
        if category: clause += " AND p.source_category=%s"; params.append(category)
        query=f"""SELECT DISTINCT ON (p.id) p.external_id,p.title,p.image_url,p.product_url,p.source_category,p.first_seen_at,p.last_seen_at,s.rank,s.price,s.currency,s.observed_at,s.evidence_json
            FROM market_radar_products p JOIN market_radar_snapshots s ON s.product_id=p.id {clause}
            ORDER BY p.id,s.observed_at DESC"""
        with self._connect() as con, con.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query,params); rows=cur.fetchall()
        rows.sort(key=lambda item:(item["rank"] is None,item["rank"] or 999))
        first=min((item["first_seen_at"] for item in rows),default=None)
        return {"marketplace":"MERCADO_LIVRE","category":category,"limit":limit,"history_available_from":first.isoformat() if first else None,"history_complete":False,"products":[dict(item) for item in rows[:limit]]}

    def trends(self, category: str | None = None) -> dict:
        self.migrate(); clause="WHERE marketplace='MERCADO_LIVRE'"; params=[]
        if category: clause += " AND category=%s"; params.append(category)
        with self._connect() as con, con.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(f"SELECT DISTINCT ON (keyword,trend_type,category) keyword,trend_type,position,category,url,observed_at,source_window FROM market_radar_trends {clause} ORDER BY keyword,trend_type,category,observed_at DESC",params)
            rows=cur.fetchall()
        return {"marketplace":"MERCADO_LIVRE","category":category,"source_window":"weekly","trends":[dict(item) for item in rows]}

    def enrich_existing(self, adapter, *, category: str, limit: int = 20) -> dict:
        """Re-read only official detail endpoints for persisted ranking identities."""
        self.migrate()
        with self._connect() as con, con.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("""SELECT p.id,p.external_id,p.title,s.rank,s.evidence_json FROM market_radar_products p
                JOIN market_radar_snapshots s ON s.product_id=p.id WHERE p.marketplace='MERCADO_LIVRE'
                AND p.source_category=%s ORDER BY s.rank NULLS LAST LIMIT %s""", (category,min(max(1,limit),20)))
            rows=cur.fetchall()
        rankings=[]
        for row in rows:
            evidence=row["evidence_json"] if isinstance(row["evidence_json"],dict) else json.loads(row["evidence_json"])
            rankings.append({"id":row["external_id"],"position":row["rank"],"type":evidence.get("ranking_type")})
        resolved=adapter.resolve_rankings(rankings)
        recovered=remaining=0; reasons={}
        with self._connect() as con, con.cursor() as cur:
            for row, ranking in zip(rows,rankings):
                detail=resolved.get(ranking["id"]) or {}
                title=detail.get("title") or detail.get("name")
                pictures=detail.get("pictures") or []
                image=detail.get("thumbnail") or detail.get("thumbnail_id")
                if not image and pictures and isinstance(pictures[0],dict): image=pictures[0].get("secure_url") or pictures[0].get("url")
                price=detail.get("price")
                url=detail.get("permalink")
                meaningful=bool(title or image or price is not None or url)
                evidence=row["evidence_json"] if isinstance(row["evidence_json"],dict) else json.loads(row["evidence_json"])
                evidence["detail_resolved"]=meaningful
                evidence["detail_rechecked_at"]=_now()
                if not meaningful:
                    outcome=getattr(adapter, "last_resolution_outcomes", {}).get(ranking["id"], "EXTERNAL_FAILURE")
                    reason=("USER_PRODUCT_" if ranking.get("type")=="USER_PRODUCT" else "PRODUCT_") + outcome
                    evidence["detail_reason"]=reason; reasons[reason]=reasons.get(reason,0)+1; remaining+=1
                else:
                    evidence.pop("detail_reason",None); recovered+=1
                cur.execute("UPDATE market_radar_products SET title=COALESCE(%s,title),image_url=COALESCE(%s,image_url),product_url=COALESCE(%s,product_url) WHERE id=%s",(title,image,url,row["id"]))
                cur.execute("UPDATE market_radar_snapshots SET price=COALESCE(%s,price),currency=COALESCE(%s,currency),product_url=COALESCE(%s,product_url),evidence_json=%s::jsonb WHERE product_id=%s AND rank=%s",(price,detail.get("currency_id"),url,json.dumps(evidence,ensure_ascii=False),row["id"],row["rank"]))
        return {"category":category,"checked":len(rows),"recovered":recovered,"remaining_partial":remaining,"reasons":reasons}


def hosted_market_store() -> PostgresMarketStore | None:
    url=os.environ.get("OAUTH_DATABASE_URL")
    return PostgresMarketStore(url) if url else None
