from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Marketplace(str, Enum):
    MERCADO_LIVRE = "MERCADO_LIVRE"
    SHOPEE = "SHOPEE"
    ALIEXPRESS = "ALIEXPRESS"
    ALIBABA = "ALIBABA"
    SHEIN = "SHEIN"


class SourceType(str, Enum):
    OFFICIAL_API = "OFFICIAL_API"
    OFFICIAL_RANKING = "OFFICIAL_RANKING"
    PUBLIC_PAGE = "PUBLIC_PAGE"
    THIRD_PARTY_PROVIDER = "THIRD_PARTY_PROVIDER"


class SourceConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class Movement(str, Enum):
    NEW_ENTRY = "NEW_ENTRY"
    UP = "UP"
    DOWN = "DOWN"
    STABLE = "STABLE"
    LEFT_TOP = "LEFT_TOP"
    UNKNOWN = "UNKNOWN"


class Category(str, Enum):
    CASA = "casa"
    COZINHA = "cozinha"
    LIMPEZA = "limpeza"
    BELEZA = "beleza"
    MODA = "moda"
    ELETRONICOS = "eletronicos"
    GADGETS = "gadgets"
    OUTROS = "outros"


@dataclass(frozen=True)
class MarketplaceCapabilities:
    supports_rank: bool = False
    supports_category: bool = False
    supports_price: bool = False
    supports_sales_count: bool = False
    supports_order_count: bool = False
    supports_views: bool = False
    supports_rating: bool = False
    supports_reviews: bool = False
    supports_stock: bool = False
    supports_supplier: bool = False
    supports_moq: bool = False
    supports_source_window: bool = False
    supports_product_url: bool = False
    supports_image: bool = False
    authentication_required: bool = False
    official_api_available: bool = False


@dataclass(frozen=True)
class NormalizedProduct:
    marketplace: Marketplace
    external_id: str
    title: str
    normalized_title: str
    brand: str | None = None
    category: Category | None = None
    source_category: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    seller_name: str | None = None


@dataclass(frozen=True)
class MarketplaceProductObservation:
    product: NormalizedProduct
    observed_at: str
    rank: int | None = None
    price: float | None = None
    currency: str | None = None
    sales_count: int | None = None
    order_count: int | None = None
    views: int | None = None
    rating: float | None = None
    reviews: int | None = None
    stock: int | None = None
    source_type: SourceType = SourceType.PUBLIC_PAGE
    source_confidence: SourceConfidence = SourceConfidence.LOW
    source_window: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
