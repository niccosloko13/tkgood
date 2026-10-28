"""Offline-only product import. Never opens remote URLs or persists official snapshots."""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .models import Marketplace, MarketplaceProductObservation, NormalizedProduct, SourceConfidence, SourceType
from .normalization import normalize_currency, normalize_number, normalize_text, normalized_title

MAX_BYTES = 2_000_000
MAX_RECORDS = 20
MAX_FIELD_LENGTH = 2000
SUPPORTED = {".json", ".jsonl", ".csv", ".html", ".htm"}
PLATFORMS = {"shopee": Marketplace.SHOPEE, "aliexpress": Marketplace.ALIEXPRESS}


class OfflineImportError(ValueError):
    pass


class _LocalProductsHTML(HTMLParser):
    """Read only local JSON-LD Product objects; never execute HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_jsonld = False
        self.current: list[str] = []
        self.products: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        self.in_jsonld = tag.lower() == "script" and attrs_map.get("type", "").lower() == "application/ld+json"
        if self.in_jsonld:
            self.current = []

    def handle_data(self, data: str) -> None:
        if self.in_jsonld:
            self.current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "script" or not self.in_jsonld:
            return
        self.in_jsonld = False
        try:
            root = json.loads("".join(self.current))
        except (json.JSONDecodeError, ValueError):
            return
        nodes = root if isinstance(root, list) else [root]
        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("@graph"), list):
                nodes.extend(n for n in node["@graph"] if isinstance(n, dict))
            if not isinstance(node, dict):
                continue
            types = node.get("@type", [])
            types = [types] if isinstance(types, str) else types
            if "Product" in types:
                offer = node.get("offers")
                if isinstance(offer, list):
                    offer = next((o for o in offer if isinstance(o, dict)), {})
                offer = offer if isinstance(offer, dict) else {}
                images = node.get("image")
                self.products.append({
                    "name": node.get("name"), "url": node.get("url"),
                    "image": images[0] if isinstance(images, list) and images else images,
                    "price": offer.get("price"), "currency": offer.get("priceCurrency"),
                    "id": node.get("sku") or node.get("productID"),
                    "description": node.get("description"),
                })


def _safe_url(value: Any, *, marketplace: Marketplace) -> str | None:
    if not isinstance(value, str) or len(value) > MAX_FIELD_LENGTH:
        return None
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = {
        Marketplace.SHOPEE: ("shopee.com.br", "shopee.sg", "shopee.co.id", "shopee.com.my",
                             "shopee.co.th", "shopee.vn", "shopee.ph", "shopee.tw", "shopee.com.mx"),
        Marketplace.ALIEXPRESS: ("aliexpress.com", "aliexpress.us", "aliexpress.ru"),
    }[marketplace]
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        return None
    if not any(host == root or host.endswith("." + root) for root in allowed):
        return None
    return value.strip().split("#", 1)[0]


def _image(value: Any) -> str | None:
    if isinstance(value, list):
        return next((v for v in value if isinstance(v, str) and v.startswith("https://")), None)
    return value if isinstance(value, str) and value.startswith("https://") else None


def _first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] is not None and record[key] != "":
            return record[key]
    return None


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.is_symlink() or path.suffix.lower() not in SUPPORTED:
        raise OfflineImportError("Unsupported local input")
    if path.stat().st_size > MAX_BYTES:
        raise OfflineImportError("Input exceeds 2 MB")
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise OfflineImportError("Input exceeds 2 MB")
    try:
        raw = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise OfflineImportError("Input must be UTF-8") from exc
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                parsed = parsed.get("products", [parsed])
        elif suffix == ".jsonl":
            parsed = [json.loads(line) for line in raw.splitlines() if line.strip()]
        elif suffix == ".csv":
            parsed = list(csv.DictReader(io.StringIO(raw)))
        else:
            parser = _LocalProductsHTML()
            parser.feed(raw)
            parsed = parser.products
    except (ValueError, csv.Error) as exc:
        raise OfflineImportError("Malformed local file") from exc
    if not isinstance(parsed, list) or len(parsed) > MAX_RECORDS:
        raise OfflineImportError("Expected at most 20 product records")
    if not all(isinstance(item, dict) for item in parsed):
        raise OfflineImportError("Product entries must be objects")
    return parsed


def import_offline_file(path: str | Path, *, marketplace: str,
                        source_category: str | None = None,
                        fixture: bool = False) -> list[MarketplaceProductObservation]:
    """Normalize user-supplied lawful files only, without network or storage writes.

    Imported records are not verified marketplace rankings. No sales, view,
    conversion or rank metrics are inferred. Credentials and HTML scripts are
    never evaluated. Callers must arrange any persistent import separately.
    """
    platform = PLATFORMS.get(marketplace.strip().lower())
    if platform is None:
        raise OfflineImportError("Expected shopee or aliexpress")
    path = Path(path)
    items = _records(path)
    results: list[MarketplaceProductObservation] = []
    seen: set[str] = set()
    observed_at = datetime.now(timezone.utc).isoformat()
    for item in items:
        title = normalize_text(_first(item, "title", "name", "product_title"))
        if not title or len(title) > 300:
            continue
        url = _safe_url(_first(item, "url", "link", "product_url", "product_detail_url"), marketplace=platform)
        external_id = str(_first(item, "product_id", "id", "item_id", "sku") or "").strip()
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,100}", external_id):
            continue
        key = platform.value + ":" + external_id
        if key in seen:
            continue
        seen.add(key)
        price = normalize_number(_first(item, "price", "sale_price", "target_sale_price"))
        if isinstance(price, (int, float)) and price < 0:
            price = None
        currency = normalize_currency(_first(item, "currency", "priceCurrency", "sale_price_currency"))
        if currency and not re.fullmatch(r"[A-Z]{3}", currency):
            currency = None
        product = NormalizedProduct(
            platform, external_id, title, normalized_title(title) or title.casefold(),
            source_category=normalize_text(source_category or str(item.get("category") or "")),
            product_url=url,
            image_url=_image(_first(item, "image", "images", "image_url", "product_main_image_url")),
        )
        results.append(MarketplaceProductObservation(
            product=product, observed_at=observed_at, price=float(price) if price is not None else None,
            currency=currency, source_type=SourceType.THIRD_PARTY_PROVIDER,
            source_confidence=SourceConfidence.LOW,
            evidence={
                "import_origin": "FIXTURE" if fixture else "IMPORTED_FILE",
                "ranking_available": False, "not_live": True,
                "verified_sales_48h": None, "verified_visitors_48h": None,
                "source_format": path.suffix.lower().lstrip("."),
                "source_fields": sorted(k for k in item if isinstance(k, str))[:80],
            },
        ))
    return results
