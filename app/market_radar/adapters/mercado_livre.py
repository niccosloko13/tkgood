"""Official Mercado Livre (MLB) adapter. No HTML scraping is used here."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..capabilities import source_confidence
from ..models import (Marketplace, MarketplaceCapabilities, MarketplaceProductObservation,
                      NormalizedProduct, SourceType)
from ..normalization import normalize_currency, normalize_number, normalize_text, normalize_url, normalized_title
from .base import MarketplaceAdapter


class MercadoLivreError(RuntimeError):
    code = "EXTERNAL_FAILURE"


class MercadoLivreAuthError(MercadoLivreError):
    code = "AUTH_REQUIRED"


class MercadoLivreCategoryNotRanked(MercadoLivreError):
    code = "CATEGORY_NOT_RANKED"


class MercadoLivreTransportError(MercadoLivreError):
    code = "NETWORK_FAILURE"


class MercadoLivreClient:
    base_url = "https://api.mercadolibre.com"

    def __init__(self, access_token: str | None = None, request_json: Callable[[str, dict[str, str]], Any] | None = None):
        if access_token is None:
            # Tokens remain server-side; hosted environments load them from the
            # encrypted OAuth store while local development keeps its .env flow.
            from ..mercado_livre_auth import config
            access_token = config().access_token
        self.access_token = access_token
        self._request_json = request_json

    @property
    def configured(self) -> bool:
        return bool(self.access_token)

    def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        if not self.configured:
            raise MercadoLivreAuthError("Mercado Livre access token is not configured")
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params, safe=',.') }"
        headers = {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}
        if self._request_json:
            return self._request_json(url, headers)
        try:
            with urlopen(Request(url, headers=headers), timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 401:
                raise MercadoLivreAuthError("Mercado Livre authorization is required") from exc
            if exc.code == 404 and (path.startswith("/highlights/") or path.startswith("/categories/")):
                raise MercadoLivreCategoryNotRanked("The category does not expose a best-seller ranking") from exc
            raise MercadoLivreError(f"Mercado Livre API returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise MercadoLivreTransportError("Mercado Livre API could not be reached") from exc

    def probe(self) -> dict:
        """Validate the token using the official authenticated identity endpoint."""
        payload = self.get("/users/me")
        if not isinstance(payload, dict) or not payload.get("id"):
            raise MercadoLivreError("Malformed Mercado Livre account probe")
        return {"authenticated": True, "site_id": payload.get("site_id")}


class MercadoLivreAdapter(MarketplaceAdapter):
    marketplace = Marketplace.MERCADO_LIVRE
    source_type = SourceType.OFFICIAL_API

    def __init__(self, client: MercadoLivreClient | None = None):
        self.client = client or MercadoLivreClient()
        self.available = self.client.configured

    def capabilities(self) -> MarketplaceCapabilities:
        return MarketplaceCapabilities(supports_rank=True, supports_category=True, supports_price=True,
          supports_product_url=True, supports_image=True, authentication_required=True, official_api_available=True)

    def category_info(self, category_id: str) -> dict:
        data = self.client.get(f"/categories/{category_id}")
        return {"id": data.get("id"), "name": data.get("name"), "is_leaf": not bool(data.get("children_categories"))}

    def fetch_top_products(self, *, category: str | None = None, limit: int = 20) -> list[MarketplaceProductObservation]:
        if not category:
            raise ValueError("A Mercado Livre category_id is required")
        category_info = self.category_info(category)
        if not category_info.get("is_leaf"):
            raise MercadoLivreCategoryNotRanked("Best-seller rankings require a Mercado Livre leaf category")
        payload = self.client.get(f"/highlights/MLB/category/{category}")
        content = payload.get("content") if isinstance(payload, dict) else None
        if not isinstance(content, list):
            raise MercadoLivreError("Malformed highlights response")
        observed_at = datetime.now(timezone.utc).isoformat()
        rankings = [entry for entry in content[:min(max(1, limit), 20)] if isinstance(entry, dict) and entry.get("id")]
        resolved = self.resolve_rankings(rankings)
        observations: list[MarketplaceProductObservation] = []
        for entry in rankings:
            detail = resolved.get(str(entry["id"]))
            observations.append(self._observation(entry, detail, category, observed_at))
        return observations

    def resolve_rankings(self, rankings: list[dict]) -> dict[str, dict | None]:
        result: dict[str, dict | None] = {}
        item_ids = [str(row["id"]) for row in rankings if row.get("type") == "ITEM"]
        if item_ids:
            for entry in self._bulk_items(item_ids):
                result[entry["id"]] = entry
        for row in rankings:
            external_id = str(row["id"])
            kind = row.get("type")
            if kind == "ITEM":
                result.setdefault(external_id, None)
                continue
            try:
                result[external_id] = self._single_product(external_id, kind)
            except MercadoLivreError:
                result[external_id] = None
        return result

    def _bulk_items(self, ids: list[str]) -> list[dict]:
        payload = self.client.get("/items/bulk", {"ids": ",".join(ids), "attributes": "body.id,body.title,body.price,body.currency_id,body.permalink,body.thumbnail,body.category_id,body.condition,body.seller_id"})
        if not isinstance(payload, list):
            return []
        return [row["body"] for row in payload if isinstance(row, dict) and row.get("status_code", row.get("code")) == 200 and isinstance(row.get("body"), dict) and row["body"].get("id")]

    def _single_product(self, external_id: str, kind: str | None) -> dict | None:
        endpoint = "/products/" if kind == "PRODUCT" else "/user-products/" if kind == "USER_PRODUCT" else None
        if endpoint is None:
            return None
        payload = self.client.get(f"{endpoint}{external_id}")
        return payload if isinstance(payload, dict) else None

    def _observation(self, ranking: dict, detail: dict | None, category_id: str, observed_at: str) -> MarketplaceProductObservation:
        detail = detail or {}
        title = normalize_text(detail.get("title")) or f"Mercado Livre {ranking['id']}"
        pictures = detail.get("pictures") or []
        image = detail.get("thumbnail") or detail.get("thumbnail_id")
        if not image and pictures and isinstance(pictures[0], dict): image = pictures[0].get("secure_url") or pictures[0].get("url")
        seller = detail.get("seller_nickname") or detail.get("seller_name")
        product = NormalizedProduct(Marketplace.MERCADO_LIVRE, str(ranking["id"]), title, normalized_title(title) or title.lower(),
          category=None, source_category=detail.get("category_id") or category_id, image_url=normalize_url(image),
          product_url=normalize_url(detail.get("permalink")), seller_name=normalize_text(seller))
        return MarketplaceProductObservation(product=product, observed_at=observed_at, rank=ranking.get("position") if isinstance(ranking.get("position"), int) else None,
          price=normalize_number(detail.get("price")), currency=normalize_currency(detail.get("currency_id")),
          source_type=SourceType.OFFICIAL_API, source_confidence=source_confidence(SourceType.OFFICIAL_API),
          source_window=None, evidence={"ranking_type": ranking.get("type"), "source_category_id": category_id,
            "source_context": f"/highlights/MLB/category/{category_id}", "detail_resolved": bool(detail)})

    def fetch_trends(self, *, category: str | None = None) -> list[dict]:
        path = f"/trends/MLB/{category}" if category else "/trends/MLB"
        payload = self.client.get(path)
        if not isinstance(payload, list):
            raise MercadoLivreError("Malformed trends response")
        observed_at = datetime.now(timezone.utc).isoformat()
        kinds = ((0, 10, "FASTEST_GROWING"), (10, 30, "MOST_WANTED"), (30, 50, "POPULAR_TREND"))
        trends = []
        for start, end, trend_type in kinds:
            for position, row in enumerate(payload[start:end], start=start + 1):
                if isinstance(row, dict) and normalize_text(row.get("keyword")):
                    trends.append({"marketplace": Marketplace.MERCADO_LIVRE.value, "keyword": normalize_text(row["keyword"]), "trend_type": trend_type,
                      "position": position, "category": category, "url": normalize_url(row.get("url")), "observed_at": observed_at,
                      "source_type": SourceType.OFFICIAL_API.value, "source_window": "weekly", "evidence": {"source_context": path}})
        return trends
