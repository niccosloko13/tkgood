"""Auditable bestseller observation windows; never confuse ranks with units sold."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

def build_window(rows: list[dict], hours: int, now: datetime | None = None,
                 sort: str = "ranking", min_rank: int | None = None, limit: int = 100) -> dict:
    if hours not in (48,168,720):
        raise ValueError("Invalid period")
    if sort not in ("ranking","recent","price_low","price_high"):
        raise ValueError("Unsupported ordering")
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    latest = {}
    for raw in rows:
        item = dict(raw)
        timestamp = item.get("observed_at")
        if isinstance(timestamp, str):
            try: timestamp=datetime.fromisoformat(timestamp.replace("Z","+00:00"))
            except ValueError: continue
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or not start <= timestamp <= now:
            continue
        rank = item.get("rank")
        if min_rank is not None and (not isinstance(rank,int) or rank>min_rank):
            continue
        key=(item.get("marketplace"),item.get("external_id"),item.get("source_category"))
        if key not in latest or timestamp > latest[key]["observed_at"]:
            item["observed_at"]=timestamp
            latest[key]=item
    items=list(latest.values())
    if sort=="ranking": items.sort(key=lambda i:(i.get("rank") is None,i.get("rank") or 10**9,-i["observed_at"].timestamp()))
    elif sort=="recent": items.sort(key=lambda i:i["observed_at"],reverse=True)
    elif sort=="price_low": items.sort(key=lambda i:(i.get("price") is None,float(i["price"]) if i.get("price") is not None else float("inf")))
    else: items.sort(key=lambda i:(i.get("price") is None,-float(i["price"]) if i.get("price") is not None else float("inf")))
    result=[]
    for entry in items[:max(1,min(limit,100))]:
        entry["observed_at"]=entry["observed_at"].isoformat()
        entry["units_sold_in_window"]=None
        entry["visits_in_window"]=None
        entry["units_sold_source"]="NOT_AVAILABLE"
        entry["visits_source"]="NOT_AVAILABLE"
        entry["ranking_is_sales_count"]=False
        result.append(entry)
    return {"window_hours":hours,"window_start":start.isoformat(),"window_end":now.isoformat(),
            "observation_count":len(items),"products":result,"sales_count_available":False,
            "visits_available":False,"complete_window":False,
            "notice":"Ranking oficial por categoria observado nesta janela; NÃO representa unidades vendidas ou visitas do período."}
