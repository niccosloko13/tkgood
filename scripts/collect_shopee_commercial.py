"""Fetch Shopee BR commercial data from authorized Nexscope account to Neon.
Never uses browser bypass or unauthenticated marketplace endpoints.
Requires NEXSCOPE_API_KEY and OAUTH_DATABASE_URL only in operator process.
"""
from __future__ import annotations
import json,os,sys
from datetime import datetime,timezone
from urllib import request,error
from app.market_radar.commercial_metrics import hosted_commercial_store,nexscope_shopee_rows

URL="https://api.nexscope.ai/yy/shopee/getProductInfos"

def run(*, keyword:str="", page_size:int=10, dry_run:bool=False)->dict:
    if not 1<=page_size<=20:raise ValueError("Maximum 20 products per request")
    token=os.environ.get("NEXSCOPE_API_KEY")
    if not token or len(token)<12:raise RuntimeError("NEXSCOPE_API_KEY is not configured")
    args={"station":"BR","page":1,"pageSize":page_size,"orderBy":"sold","orderByType":"DESC"}
    if keyword:
        args["keyword"]=keyword[:100]
        args["keywordType"]=2
    req=request.Request(URL,data=json.dumps(args).encode(),method="POST",
          headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    with request.urlopen(req,timeout=35) as resp:
        envelope=json.load(resp)
    if not isinstance(envelope,dict) or ("code" in envelope and envelope["code"]!=0):
        raise RuntimeError("Provider returned unsuccessful response")
    # Real response envelope may differ from the GitHub fixture.
    data=envelope.get("data",envelope)
    if not isinstance(data,dict) or not isinstance(data.get("products"),list):
        raise RuntimeError("Provider response shape not validated. No rows inserted.")
    observed=datetime.now(timezone.utc)
    rows=nexscope_shopee_rows(data,observed_at=observed)
    if dry_run:return {"products":len({r["product_id"] for r in rows}),"metrics":len(rows),"persisted":False}
    store=hosted_commercial_store()
    if not store:raise RuntimeError("OAUTH_DATABASE_URL not configured")
    for start in range(0,len(rows),100):
        store.save(rows[start:start+100])
    return {"products":len({r["product_id"] for r in rows}),"metrics":len(rows),"persisted":True}

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--keyword",default="")
    parser.add_argument("--limit",type=int,default=10)
    parser.add_argument("--dry-run",action="store_true")
    opts=parser.parse_args()
    try:
        result=run(keyword=opts.keyword,page_size=opts.limit,dry_run=opts.dry_run)
        print(json.dumps(result))
    except (RuntimeError,ValueError,error.URLError,TimeoutError) as exc:
        print("Commercial collection unavailable: "+type(exc).__name__+"; credentials and payloads suppressed.",file=sys.stderr)
        sys.exit(2)
