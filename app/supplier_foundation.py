"""Offline evidence contract only; no provider, network, matching algorithm or writes."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator


class ShippingEvidence(BaseModel):
    model_config=ConfigDict(extra='forbid')
    price:Decimal|None=Field(default=None,ge=0,allow_inf_nan=False)
    currency:str|None=Field(default=None,pattern=r'^[A-Z]{3}$')
    destination_country:str|None=Field(default=None,pattern=r'^[A-Z]{2}$')
    terms:str|None=Field(default=None,max_length=2000)


class SupplierListingEvidence(BaseModel):
    model_config=ConfigDict(extra='forbid')
    product_entity_id:str|None=Field(default=None,max_length=128)
    identity_hypothesis_id:str|None=Field(default=None,max_length=128)
    provider:str=Field(min_length=1,max_length=100)
    listing_title:str=Field(min_length=1,max_length=1000)
    listing_url:str=Field(max_length=4000)
    price:Decimal|None=Field(default=None,ge=0,allow_inf_nan=False)
    currency:str|None=Field(default=None,pattern=r'^[A-Z]{3}$')
    min_order:int|None=Field(default=None,ge=1)
    shipping:ShippingEvidence|None=None
    country:str|None=Field(default=None,pattern=r'^[A-Z]{2}$')
    rating:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    rating_scale:float=Field(default=5,gt=0,allow_inf_nan=False)
    orders:int|None=Field(default=None,ge=0)
    observed_at:datetime
    match_confidence:float|None=Field(default=None,ge=0,le=1,allow_inf_nan=False)
    review_status:Literal['unreviewed','reviewed','rejected']='unreviewed'

    @field_validator('listing_url')
    @classmethod
    def public_reference(cls,value):
        u=urlsplit(value)
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
            raise ValueError('An HTTP(S) reference without credentials is required; it is never fetched')
        return value

    @field_validator('observed_at')
    @classmethod
    def timezone_required(cls,value):
        if value.tzinfo is None or value.utcoffset() is None:raise ValueError('Timezone required')
        return value

    @model_validator(mode='after')
    def coherent_units(self):
        if self.price is not None and self.currency is None:raise ValueError('Currency required with price')
        if self.rating is not None and self.rating>self.rating_scale:raise ValueError('Rating exceeds declared scale')
        if self.shipping and self.shipping.price is not None and self.shipping.currency is None:raise ValueError('Shipping currency required with price')
        return self
