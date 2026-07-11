"""Normalización de datos extraídos."""

import re
from datetime import datetime
from html import unescape
from typing import Any


def clean_text(value: str) -> str:
    """Trim, unescape y colapsa espacios."""
    text = unescape(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_record(data: dict[str, Any]) -> dict[str, Any]:
    """Normaliza valores string en un registro."""
    result: dict[str, Any] = {}
    for key, val in data.items():
        if isinstance(val, str):
            result[key] = clean_text(val)
        elif isinstance(val, list):
            result[key] = [clean_text(v) if isinstance(v, str) else v for v in val]
        else:
            result[key] = val
    return result


def parse_iso_date(value: str) -> str | None:
    """Intenta convertir fecha a ISO 8601."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt).isoformat()
        except ValueError:
            continue
    return None
