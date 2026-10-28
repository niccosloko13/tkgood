"""Explicit maintenance command for the isolated Neon offline-import tables.

Uses the same OAUTH_DATABASE_URL as the hosted Market Radar, but requires the
operator to provide it through a protected runtime. No secrets are displayed.
"""
from __future__ import annotations

import argparse
import os

from app.market_radar.offline_store import MarketImportStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate", action="store_true", help="Create only isolated offline-import tables")
    parser.add_argument("--verify", action="store_true", help="Check isolated tables, without changing official rankings")
    args = parser.parse_args()
    if not args.migrate and not args.verify:
        parser.error("Choose --migrate or --verify")
    url = os.getenv("OAUTH_DATABASE_URL")
    if not url:
        print("OAUTH_DATABASE_URL unavailable. Run only in an authorized environment.")
        return 2
    store = MarketImportStore(url)
    if args.migrate:
        store.migrate()
        print("Offline import schema prepared. Official ranking tables unchanged.")
    if args.verify:
        with store._connection() as con, con.cursor() as cur:
            cur.execute("""
                SELECT
                  to_regclass('public.market_radar_offline_imports') IS NOT NULL,
                  to_regclass('public.market_radar_offline_import_products') IS NOT NULL
            """)
            tables = cur.fetchone()
            if not all(tables):
                print("Offline import schema missing; run --migrate.")
                return 2
            cur.execute("SELECT count(*) FROM market_radar_offline_imports")
            batches = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM market_radar_offline_import_products")
            products = cur.fetchone()[0]
        print(f"Offline import schema OK. Batches={batches}; imported_products={products}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
