from __future__ import annotations

from .models import Marketplace, MarketplaceCapabilities, SourceConfidence, SourceType


def default_capabilities() -> MarketplaceCapabilities:
    """No capability is assumed before an adapter documents it."""
    return MarketplaceCapabilities()


def source_confidence(source_type: SourceType) -> SourceConfidence:
    return {
        SourceType.OFFICIAL_API: SourceConfidence.HIGH,
        SourceType.OFFICIAL_RANKING: SourceConfidence.HIGH,
        SourceType.PUBLIC_PAGE: SourceConfidence.MEDIUM,
        SourceType.THIRD_PARTY_PROVIDER: SourceConfidence.LOW,
    }[source_type]


def as_dict(capabilities: MarketplaceCapabilities) -> dict[str, bool]:
    return {name: getattr(capabilities, name) for name in capabilities.__dataclass_fields__}


MARKETPLACES = tuple(Marketplace)
