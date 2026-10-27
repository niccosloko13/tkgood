from __future__ import annotations

from abc import ABC, abstractmethod

from ..capabilities import default_capabilities
from ..models import Marketplace, MarketplaceCapabilities, MarketplaceProductObservation, SourceType


class MarketplaceAdapter(ABC):
    marketplace: Marketplace
    source_type: SourceType = SourceType.PUBLIC_PAGE
    available: bool = False

    def capabilities(self) -> MarketplaceCapabilities:
        return default_capabilities()

    @abstractmethod
    def fetch_top_products(self, *, category: str | None = None, limit: int = 20) -> list[MarketplaceProductObservation]:
        """Return only observations the adapter can actually source."""
        raise NotImplementedError


class UnavailableAdapter(MarketplaceAdapter):
    def fetch_top_products(self, *, category: str | None = None, limit: int = 20) -> list[MarketplaceProductObservation]:
        raise RuntimeError("adapter unavailable")
