"""Mercado Livre category discovery and Babi category registry.

The registry deliberately contains no guessed leaf IDs. Mercado Livre makes
best-seller rankings available only for some leaf categories, so IDs are
validated against the official category endpoint before a collection runs.
"""
from __future__ import annotations

from .models import Category


BABI_CATEGORY_REGISTRY = {
    Category.CASA.value: {"label": "Casa", "official_category_ids": ()},
    Category.COZINHA.value: {"label": "Cozinha", "official_category_ids": ()},
    Category.LIMPEZA.value: {"label": "Limpeza", "official_category_ids": ()},
    Category.BELEZA.value: {"label": "Beleza", "official_category_ids": ()},
    Category.MODA.value: {"label": "Moda", "official_category_ids": ()},
    Category.ELETRONICOS.value: {"label": "Eletrônicos", "official_category_ids": ()},
    Category.GADGETS.value: {"label": "Gadgets", "official_category_ids": ()},
    Category.OUTROS.value: {"label": "Outros", "official_category_ids": ()},
}


def category_registry() -> dict:
    """Presentation-only Babi categories; official IDs are discovered, not guessed."""
    return {key: {**value, "official_category_ids": list(value["official_category_ids"])} for key, value in BABI_CATEGORY_REGISTRY.items()}
