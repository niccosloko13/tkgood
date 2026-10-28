"""Evidence-bound commercial metrics, isolated from official rankings."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any
import json
import os
import psycopg
from psycopg.rows import dict_row

ALLOWED = {"SHOPEE", "ALIEXPRESS", "MERCADO_LIVRE", "TIKTOK_SHOP"}
KINDS = {"ACTUAL_PROVIDER", "ESTIMATED_PROVIDER", "CUMULATIVE_OBSERVED"}

class CommercialStore:
    def __init__(self, url: str): self.url=url
    def connect(self): return psycopg.connect(self.url)
    def migrate(self):
        with self.connect() as con, con.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS babi_commercial_metrics (
                id BIGSERIAL PRIMARY KEY,
                marketplace TEXT NOT NULL,
                product_id TEXT NOT NULL,
                title TEXT NOT NULL,
                image_url TEXT,
                product_url TEXT,
                category TEXT,
                price NUMERIC,
                currency TEXT,
                seller_name TEXT,
                rating NUMERIC,
                rating_count BIGINT,
                observed_at TIMESTAMPTZ NOT NULL,
                window_start TIMESTAMPTZ,
                window_end TIMESTAMPTZ,
                metric_name TEXT NOT NULL,
                metric_value NUMERIC NOT NULL CHECK(metric_value >= 0),
                metric_kind TEXT NOT NULL,
                provider TEXT NOT NULL,
                evidence JSONB NOT NULL,
                UNIQUE(marketplace,product_id,metric_name,metric_kind,provider,observed_at)
            )""")
            cur.execute("CREATE INDEX IF NOT EXISTS babi_commercial_metrics_lookup_idx ON babi_commercial_metrics(marketplace,metric_name,observed_at DESC)")
    def save(self, items: list[dict]) -> int:
        if not 1<=len(items)<=100: raise ValueError("Expected 1-100 commercial observations")
        self.migrate()
        with self.connect() as con, con.cursor() as cur:
            for item in items:
                if item["marketplace"] not in ALLOWED or item["metric_kind"] not in KINDS:
                    raise ValueError("Unsupported observation")
                if item["metric_name"] not in {"sold_30d","estimated_sold_30d","historical_sold","views_total","revenue_30d"}:
                    raise ValueError("Unsupported metric")
                if Decimal(str(item["metric_value"]))<0: raise ValueError("Negative counter")
                cur.execute("""INSERT INTO babi_commercial_metrics
                    (marketplace,product_id,title,image_url,product_url,category,price,currency,seller_name,
                     rating,rating_count,observed_at,window_start,window_end,metric_name,metric_value,
                     metric_kind,provider,evidence)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT(marketplace,product_id,metric_name,metric_kind,provider,observed_at)
                    DO UPDATE SET metric_value=EXCLUDED.metric_value,evidence=EXCLUDED.evidence""",
                    (item["marketplace"],item["product_id"],item["title"],item.get("image_url"),
                     item.get("product_url"),item.get("category"),item.get("price"),item.get("currency"),
                     item.get("seller_name"),item.get("rating"),item.get("rating_count"),item["observed_at"],
                     item.get("window_start"),item.get("window_end"),item["metric_name"],
                     item["metric_value"],item["metric_kind"],item["provider"],
                     json.dumps(item.get("evidence",{}),ensure_ascii=False)))
        return len(items)
    def ranking(self, *, marketplace: str, metric: str, limit: int = 50) -> dict:
        if marketplace not in ALLOWED or metric not in {"sold_30d","estimated_sold_30d","historical_sold","views_total","revenue_30d"}:
            raise ValueError("Invalid filters")
        self.migrate()
        with self.connect() as con, con.cursor(row_factory=dict_row) as cur:
            cur.execute("""SELECT DISTINCT ON(product_id,metric_kind,provider)
                product_id,title,image_url,product_url,category,price,currency,seller_name,rating,rating_count,
                observed_at,window_start,window_end,metric_name,metric_value,metric_kind,provider
                FROM babi_commercial_metrics
                WHERE marketplace=%s AND metric_name=%s
                ORDER BY product_id,metric_kind,provider,observed_at DESC""",(marketplace,metric))
            rows=cur.fetchall()
        for row in rows:
            for k in ("observed_at","window_start","window_end"):
                if row[k] is not None: row[k]=row[k].isoformat()
            for k in ("price","rating","metric_value"):
                if row[k] is not None: row[k]=float(row[k])
        rows.sort(key=lambda r:r["metric_value"],reverse=True)
        return {"marketplace":marketplace,"metric":metric,"products":rows[:max(1,min(limit,50))],
                "total":len(rows),"observed_not_live":True,
                "note":"Dados do fornecedor rotulados com janela e tipo. Vendas de 48h dependem de snapshots comparáveis."}

def cumulative_growth(samples: list[dict], *, hours: int, now: datetime | None = None) -> list[dict]:
    """Only differences between SAME-source, SAME-metric cumulative counters.

    Compare nearest measurements bounding the requested period; otherwise
    report unavailable rather than treating a shorter interval as full-window.
    """
    if hours not in (48,168,720): raise ValueError("Unsupported growth window")
    now=now or datetime.now(timezone.utc)
    cutoff=now-timedelta(hours=hours)
    groups={}
    for raw in samples:
        if raw.get("metric_name") not in {"historical_sold","views_total"}: continue
        at=raw.get("observed_at")
        if isinstance(at,str):
            try: at=datetime.fromisoformat(at.replace("Z","+00:00"))
            except ValueError: continue
        if not isinstance(at,datetime) or at.tzinfo is None: continue
        key=(raw.get("marketplace"),raw.get("product_id"),raw.get("metric_name"),raw.get("provider"))
        groups.setdefault(key,[]).append({**raw,"observed_at":at})
    result=[]
    for key,entries in groups.items():
        baseline=[v for v in entries if v["observed_at"]<=cutoff]
        latest=[v for v in entries if cutoff<v["observed_at"]<=now]
        if not baseline or not latest:continue
        start=max(baseline,key=lambda v:v["observed_at"])
        end=max(latest,key=lambda v:v["observed_at"])
        a,b=Decimal(str(start["metric_value"])),Decimal(str(end["metric_value"]))
        if b<a:continue
        result.append({"marketplace":key[0],"product_id":key[1],"metric":key[2],
                       "provider":key[3],"growth":float(b-a),
                       "growth_pct":float((b-a)/a*100) if a>0 else None,
                       "baseline_at":start["observed_at"].isoformat(),
                       "latest_at":end["observed_at"].isoformat(),
                       "sampled_hours":round((end["observed_at"]-start["observed_at"]).total_seconds()/3600,2),
                       "requested_hours":hours,
                       "measurement":"COUNTER_DELTA_OBSERVED",
                       "note":"Diferença entre contadores observados; não representa necessariamente todas as vendas no período."})
    result.sort(key=lambda v:v["growth"],reverse=True)
    return result

def nexscope_shopee_rows(payload: dict, *, observed_at: datetime, provider: str="NEXSCOPE_YOUYING") -> list[dict]:
    """Parse a SUCCESSFUL provider data payload, never a documentation fixture."""
    if not isinstance(payload,dict): raise ValueError("Invalid provider data")
    products=payload.get("products")
    if not isinstance(products,list) or len(products)>100: raise ValueError("Missing or oversized product list")
    result=[]
    for p in products:
        if not isinstance(p,dict) or not str(p.get("pid","")).strip() or not p.get("title"): continue
        common={"marketplace":"SHOPEE","product_id":str(p["pid"]),"title":str(p["title"])[:500],
                "image_url":p.get("imageUrl"),"product_url":p.get("productUrl"),
                "price":p.get("price"),"currency":"BRL","category":str(p.get("cid") or ""),
                "seller_name":p.get("shopName"),"rating":p.get("rating"),
                "rating_count":p.get("ratings"),"observed_at":observed_at,
                "provider":provider,"evidence":{"origin":"PROVIDER_API","raw_fields":list(p.keys())[:70]}}
        metrics=(("sold","sold_30d","ACTUAL_PROVIDER",30),
                 ("estimateSold","estimated_sold_30d","ESTIMATED_PROVIDER",30),
                 ("historicalSold","historical_sold","CUMULATIVE_OBSERVED",None),
                 ("viewCount","views_total","CUMULATIVE_OBSERVED",None),
                 ("payment","revenue_30d","ACTUAL_PROVIDER",30))
        for key,name,kind,days in metrics:
            v=p.get(key)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or v<0 or v!=v: continue
            result.append({**common,"metric_name":name,"metric_kind":kind,"metric_value":v,
                           "window_start":observed_at-timedelta(days=days) if days else None,
                           "window_end":observed_at if days else None,
                           "evidence":{**common["evidence"],"provider_field":key,
                                       "provider_period":"rolling_30_days" if days else "unspecified_cumulative"}})
    return result

def hosted_commercial_store():
    url=os.environ.get("OAUTH_DATABASE_URL")
    return CommercialStore(url) if url else None
