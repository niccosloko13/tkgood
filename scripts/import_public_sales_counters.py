"""Import verified, free public product counter observations into Babi Neon.

The operator reviews public listings and creates JSON/JSONL observations.
This tool never scrapes sites, pays a provider, or fabricates volumes.
"""
import argparse
import os
from app.market_radar.first_party_engine import read_file
from app.market_radar.commercial_metrics import hosted_commercial_store

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--file",required=True)
    p.add_argument("--source-id",required=True)
    p.add_argument("--origin",choices=["PUBLIC_LISTING","OWNED_SHOP_EXPORT","AUTHORIZED_EXPORT"],default="PUBLIC_LISTING")
    p.add_argument("--dry-run",action="store_true")
    args=p.parse_args()
    records=read_file(args.file,source_id=args.source_id,origin=args.origin)
    print(f"Validated observations: {len(records)}; distinct products: {len({(x['marketplace'],x['product_id']) for x in records})}")
    if args.dry_run:
        print("Dry run: no Neon writes.")
        return
    store=hosted_commercial_store()
    if not store:raise SystemExit("Neon OAUTH_DATABASE_URL required in protected operator environment")
    print(f"Saved {store.save(records)} verified counter observations.")

if __name__=="__main__":main()
