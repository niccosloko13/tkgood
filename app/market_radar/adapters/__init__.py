from .base import UnavailableAdapter
from .mercado_livre import MercadoLivreAdapter
from ..models import Marketplace


class AliExpressAdapter(UnavailableAdapter):
    marketplace = Marketplace.ALIEXPRESS


class ShopeeAdapter(UnavailableAdapter):
    marketplace = Marketplace.SHOPEE


class AlibabaAdapter(UnavailableAdapter):
    marketplace = Marketplace.ALIBABA


class SheinAdapter(UnavailableAdapter):
    marketplace = Marketplace.SHEIN


def adapters():
    return tuple(adapter() for adapter in (MercadoLivreAdapter, AliExpressAdapter, ShopeeAdapter, AlibabaAdapter, SheinAdapter))
