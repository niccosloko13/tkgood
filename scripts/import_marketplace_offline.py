"""Operator-only offline import of legitimately obtained marketplace product files.

Usage (local, with protected DB connection in environment):
    python -m scripts.import_marketplace_offline --marketplace shopee --file path/to/products.json
No browser requests, remote scraping or official ranking writes.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.market_radar.offline_import import OfflineImportError, import_offline_file
from app.market_radar.offline_store import MarketImportStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Import local marketplace file to isolated Neon tables")
    parser.add_argument("--marketplace", choices=("shopee", "aliexpress"), required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--category")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        observations = import_offline_file(
            Path(args.file), marketplace=args.marketplace,
            source_category=args.category, fixture=args.fixture,
        )
        print(f"Validated {len(observations)} imported records (no live marketplace data).")
        if args.dry_run:
            print("Dry run: no database connection or writes.")
            return 0
        url = os.getenv("OAUTH_DATABASE_URL")
        if not url:
            print("No database connection configured; nothing persisted.")
            return 2
        if not observations:
            print("No valid products; nothing persisted.")
            return 2
        store = MarketImportStore(url)
        batch = store.save(observations, source_kind="FIXTURE" if args.fixture else "IMPORTED_FILE")
        print(f"Saved isolated import batch {batch}. No official ranking rows were modified.")
        return 0
    except (OfflineImportError, ValueError) as exc:
        print(f"Import rejected: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
