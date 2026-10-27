from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    collapsed = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    return collapsed or None


def normalized_title(value: str | None) -> str | None:
    text = normalize_text(value)
    return text.casefold() if text else None


def normalize_currency(value: str | None) -> str | None:
    value = normalize_text(value)
    return value.upper() if value else None


def normalize_number(value: object) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = normalize_text(str(value))
    if not text:
        return None
    text = re.sub(r"[^0-9,.-]", "", text)
    if text.count(",") == 1 and text.count(".") >= 1:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(",") == 1:
        text = text.replace(",", ".")
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    return int(result) if result == result.to_integral() else float(result)


def normalize_url(value: str | None) -> str | None:
    value = normalize_text(value)
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ""))
