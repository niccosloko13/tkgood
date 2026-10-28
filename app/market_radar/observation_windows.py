"""Auditable window analysis: official rank movement is NOT sold units."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone

def build_window(rows: list[dict], hours: int, now: datetime | None = None,
                 sort: str = "ranking", min_rank: int | None = None, limit: int = 100) -> dict:
    if hours not in (48,168,720): raise ValueError("Invalid period")
    if sort not in ("ranking","recent","price_low","price_high","rising"): raise ValueError("Unsupported ordering")
    now=now or datetime.now(timezone.utc)
    start=now-timedelta(hours=hours)
    history={}
    for raw in rows:
        item=dict(raw)
        at=item.get("observed_at")
        if isinstance(at,str):
            try: at=datetime.fromisoformat(at.replace("Z","+00:00"))
            except ValueError: continue
        if not isinstance(at,datetime) or at.tzinfo is None or not start<=at<=now: continue
        item["observed_at"]=at
        key=(item.get("marketplace"),item.get("external_id"),item.get("source_category"))
        history.setdefault(key,[]).append(item)
    items=[]
    for samples in history.values():
        samples.sort(key=lambda v:v["observed_at"])
        first,last=samples[0],dict(samples[-1])
        if min_rank is not None and (not isinstance(last.get("rank"),int) or last["rank"]>min_rank): continue
        ranked=[sample for sample in samples if isinstance(sample.get("rank"),int) and sample["rank"]>0]
        # Position comparison requires TWO distinct timestamps, never a repeated ingestion.
        distinct={sample["observed_at"]:sample for sample in ranked}
        ordered=sorted(distinct.values(),key=lambda v:v["observed_at"])
        earliest=ordered[0] if len(ordered)>1 else None
        movement=earliest["rank"]-ordered[-1]["rank"] if earliest else None
        last.update({
            "rank_movement":movement,"rank_movement_label":"UP" if movement is not None and movement>0
              else "DOWN" if movement is not None and movement<0 else "STABLE" if movement==0 else "INSUFFICIENT_HISTORY",
            "observation_count":len(samples),"first_observed_in_window":first["observed_at"].isoformat(),
            "last_observed_in_window":last["observed_at"].isoformat(),
            "units_sold_in_window":None,"visits_in_window":None,
            "units_sold_source":"NOT_AVAILABLE","visits_source":"NOT_AVAILABLE",
            "ranking_is_sales_count":False,
        })
        items.append(last)
    if sort=="ranking": items.sort(key=lambda v:(v.get("rank") is None,v.get("rank") or 10**9,-v["observed_at"].timestamp()))
    elif sort=="recent": items.sort(key=lambda v:v["observed_at"],reverse=True)
    elif sort=="rising": items.sort(key=lambda v:(v["rank_movement"] is None,-(v["rank_movement"] or 0),v.get("rank") or 10**9))
    elif sort=="price_low": items.sort(key=lambda v:(v.get("price") is None,float(v["price"]) if v.get("price") is not None else float("inf")))
    else: items.sort(key=lambda v:(v.get("price") is None,-float(v["price"]) if v.get("price") is not None else float("inf")))
    for item in items: item["observed_at"]=item["observed_at"].isoformat()
    return {"window_hours":hours,"window_start":start.isoformat(),"window_end":now.isoformat(),
            "observation_count":len(items),"products":items[:max(1,min(limit,100))],
            "sales_count_available":False,"visits_available":False,"complete_window":False,
            "notice":"Movimentação é mudança de posição em observações oficiais, não vendas ou visitas. Dados ausentes permanecem nulos."}
