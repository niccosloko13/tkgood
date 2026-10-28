"""Free first-party evidence engine for Babi market counters.

No paid API or scraping bypass. Accepts public, documented observations from
operator-approved JSON/JSONL and calculates conservative counter growth.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone,timedelta
from decimal import Decimal,InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

ALLOWED={"SHOPEE","ALIEXPRESS","MERCADO_LIVRE","TIKTOK_SHOP"}
COUNTERS={"historical_sold","views_total"}
MAX_BYTES=2_000_000
MAX_RECORDS=100

def parse_time(value):
    if not isinstance(value,str):raise ValueError("Timestamp required")
    stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
    if stamp.tzinfo is None:raise ValueError("UTC offset required")
    return stamp.astimezone(timezone.utc)

def validate_product_link(url):
    if not isinstance(url,str) or len(url)>2048:raise ValueError("Invalid product URL")
    parts=urlsplit(url)
    if parts.scheme!="https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("HTTPS product URL required")
    host=parts.hostname.lower()
    if host not in ("shopee.com.br","www.shopee.com.br","mercadolivre.com.br","www.mercadolivre.com.br",
                    "produto.mercadolivre.com.br","pt.aliexpress.com","www.aliexpress.com","aliexpress.com",
                    "www.tiktok.com","shop.tiktok.com"):
        raise ValueError("Product domain not approved")
    return url

def normalize_observations(records, *, source_id, origin):
    if origin not in {"PUBLIC_LISTING","OWNED_SHOP_EXPORT","AUTHORIZED_EXPORT"}:raise ValueError("Invalid origin")
    if not isinstance(source_id,str) or not 3<=len(source_id)<=100:raise ValueError("Source identity required")
    if not isinstance(records,list) or not 1<=len(records)<=MAX_RECORDS:raise ValueError("Invalid batch")
    now=datetime.now(timezone.utc)
    out=[]
    for obj in records:
        if not isinstance(obj,dict):raise ValueError("Product observation must be an object")
        marketplace=obj.get("marketplace")
        if marketplace not in ALLOWED:raise ValueError("Unsupported marketplace")
        product_id=str(obj.get("product_id") or "")
        title=obj.get("title")
        metric=obj.get("metric_name")
        if not product_id or len(product_id)>128 or not isinstance(title,str) or not 1<=len(title)<=500:
            raise ValueError("Product ID/title required")
        if metric not in COUNTERS:raise ValueError("Only cumulative counters are accepted")
        try:
            raw=Decimal(str(obj["metric_value"]))
            if not raw.is_finite() or raw<0 or raw!=raw.to_integral_value():raise ValueError("Invalid count")
        except (InvalidOperation,KeyError,TypeError) as exc:raise ValueError("Valid nonnegative integer counter required") from exc
        at=parse_time(obj.get("observed_at"))
        if at>now+timedelta(minutes=5):raise ValueError("Future observation")
        url=validate_product_link(obj.get("product_url"))
        out.append({"marketplace":marketplace,"product_id":product_id,"title":title,"product_url":url,
                    "image_url":None,"category":str(obj.get("category") or "")[:128],
                    "price":None,"currency":None,"observed_at":at,
                    "metric_name":metric,"metric_value":int(raw),"metric_kind":"CUMULATIVE_OBSERVED",
                    "provider":"BABI_PUBLIC_"+source_id.upper().replace(" ","_"),
                    "evidence":{"origin":origin,"source_url":url,"counter_kind":"CUMULATIVE",
                                "collection_method":"OPERATOR_VERIFIED_FILE",
                                "recorded_at":at.isoformat()}})
    return out

def read_file(path, *,source_id,origin):
    p=Path(path)
    if p.stat().st_size>MAX_BYTES:raise ValueError("File too large")
    data=p.read_text(encoding="utf-8")
    if p.suffix.lower()==".jsonl":
        records=[json.loads(line) for line in data.splitlines() if line.strip()]
    elif p.suffix.lower()==".json":
        records=json.loads(data)
    else:raise ValueError("Only JSON and JSONL accepted")
    if isinstance(records,dict):records=records.get("products")
    return normalize_observations(records,source_id=source_id,origin=origin)
