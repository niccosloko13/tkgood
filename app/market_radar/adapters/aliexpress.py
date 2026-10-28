"""AliExpress Affiliate adapter with an explicit fixture-only transport.

The public website must not be scraped.  This adapter deliberately has no
default network client: it becomes usable only when a future, approved
AliExpress Open Platform credential supplies an official transport.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from ..capabilities import source_confidence
from ..models import (Marketplace, MarketplaceCapabilities,
                      MarketplaceProductObservation, NormalizedProduct,
                      SourceType)
from ..normalization import (normalize_currency, normalize_number,
                             normalize_text, normalize_url, normalized_title)
from .base import MarketplaceAdapter


class AliExpressAdapterError(RuntimeError):
    """A sanitized failure from the approved Affiliate API transport."""


class AliExpressAffiliateAdapter(MarketplaceAdapter):
    """Maps official Affiliate-shaped responses into Market Radar observations.

    `fetcher` is intentionally dependency-injected.  Tests use local fixtures;
    production cannot issue a request until a separately approved official API
    transport and credentials are configured.
    """

    marketplace = Marketplace.ALIEXPRESS
    source_type = SourceType.OFFICIAL_API

    def __init__(self, fetcher: Callable[..., dict[str, Any]] | None = None):
        self._fetcher = fetcher
        self.available = fetcher is not None

    def capabilities(self) -> MarketplaceCapabilities:
        return MarketplaceCapabilities(
            supports_category=True,
            supports_price=True,
            supports_product_url=True,
            supports_image=True,
            authentication_required=True,
            official_api_available=True,
        )

    def fetch_top_products(self, *, category: str | None = None,
                           limit: int = 20) -> list[MarketplaceProductObservation]:
        """Return an Affiliate hot-product list without claiming official rank.

        The official method name calls these "hot products", but its documented
        response does not establish a marketplace-wide sales rank.  Entries are
        therefore persisted as popular API results with `rank=None`.
        """
        if not self._fetcher:
            raise AliExpressAdapterError("AliExpress Affiliate API is not configured")
        payload = self._fetcher(method="get_hotproducts", category=category,
                                limit=min(max(1, limit), 20))
        return self._observations(payload, category=category,
                                  collection_kind="AFFILIATE_HOTPRODUCTS",
                                  limit=limit)

    def fetch_products(self, *, category: str | None = None, keywords: str | None = None,
                       limit: int = 20) -> list[MarketplaceProductObservation]:
        if not self._fetcher:
            raise AliExpressAdapterError("AliExpress Affiliate API is not configured")
        payload = self._fetcher(method="get_products", category=category,
                                keywords=keywords, limit=min(max(1, limit), 20))
        return self._observations(payload, category=category,
                                  collection_kind="AFFILIATE_PRODUCT_QUERY",
                                  limit=limit)

    def fetch_product_details(self, product_ids: Iterable[str]) -> list[MarketplaceProductObservation]:
        if not self._fetcher:
            raise AliExpressAdapterError("AliExpress Affiliate API is not configured")
        values = [str(value) for value in product_ids if normalize_text(str(value))]
        payload = self._fetcher(method="get_products_details", product_ids=values)
        return self._observations(payload, category=None,
                                  collection_kind="AFFILIATE_PRODUCT_DETAIL",
                                  limit=20)

    def fetch_categories(self) -> list[dict[str, str]]:
        if not self._fetcher:
            raise AliExpressAdapterError("AliExpress Affiliate API is not configured")
        payload = self._fetcher(method="get_categories")
        values = payload.get("categories", []) if isinstance(payload, dict) else []
        return [{"id": str(row["category_id"]), "name": normalize_text(row.get("category_name")) or ""}
                for row in values if isinstance(row, dict) and row.get("category_id")]

    def _observations(self, payload: dict[str, Any], *, category: str | None,
                      collection_kind: str, limit: int) -> list[MarketplaceProductObservation]:
        records = _products(payload)
        observed_at = datetime.now(timezone.utc).isoformat()
        result: list[MarketplaceProductObservation] = []
        for record in records:
            external_id = normalize_text(str(record.get("product_id") or ""))
            title = normalize_text(record.get("product_title"))
            if not external_id or not title:
                continue
            price = normalize_number(record.get("target_sale_price") or record.get("sale_price"))
            currency = normalize_currency(record.get("target_sale_price_currency") or record.get("sale_price_currency"))
            product = NormalizedProduct(
                Marketplace.ALIEXPRESS, external_id, title, normalized_title(title) or title.casefold(),
                source_category=normalize_text(record.get("second_level_category_name")) or category,
                image_url=normalize_url(record.get("product_main_image_url")),
                product_url=normalize_url(record.get("product_detail_url")),
            )
            result.append(MarketplaceProductObservation(
                product=product, observed_at=observed_at, price=price, currency=currency,
                source_type=SourceType.OFFICIAL_API,
                source_confidence=source_confidence(SourceType.OFFICIAL_API),
                evidence={"collection_kind": collection_kind, "ranking_available": False,
                          "source_fields": sorted(key for key in record if record.get(key) is not None),
                          "detail_resolved": True},
            ))
            if len(result) >= min(max(1, limit), 20):
                break
        return result


def _products(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Accept a small, documented fixture envelope or a normalized test list."""
    if not isinstance(payload, dict):
        raise AliExpressAdapterError("AliExpress returned an invalid response")
    direct = payload.get("products")
    if isinstance(direct, list):
        return [row for row in direct if isinstance(row, dict)]
    for key, response in payload.items():
        if not isinstance(key, str) or not key.startswith("aliexpress_affiliate_") or not isinstance(response, dict):
            continue
        result = response.get("resp_result", {}).get("result", {})
        products = result.get("products", {}).get("product", []) if isinstance(result, dict) else []
        if isinstance(products, dict):
            products = [products]
        if isinstance(products, list):
            return [row for row in products if isinstance(row, dict)]
    raise AliExpressAdapterError("AliExpress product list is unavailable")
