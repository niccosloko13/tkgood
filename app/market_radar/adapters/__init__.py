from .base import UnavailableAdapter
from .mercado_livre import MercadoLivreAdapter
from .aliexpress import AliExpressAffiliateAdapter
from ..models import Marketplace


class AliExpressAdapter(AliExpressAffiliateAdapter):
    """Default registry entry: no credentials/transport means unavailable."""


class ShopeeAdapter(UnavailableAdapter):
    marketplace = Marketplace.SHOPEE


class AlibabaAdapter(UnavailableAdapter):
    marketplace = Marketplace.ALIBABA


class SheinAdapter(UnavailableAdapter):
    marketplace = Marketplace.SHEIN


def adapters():
    return tuple(adapter() for adapter in (MercadoLivreAdapter, AliExpressAdapter, ShopeeAdapter, AlibabaAdapter, SheinAdapter))
