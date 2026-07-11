"""Tipos compartidos del motor de búsqueda."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class MatchResult:
    field: str
    matched_term: str
    snippet: str


def normalize_text(text: str) -> str:
    """Minúsculas sin tildes para comparación tolerante."""
    folded = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(char for char in folded if not unicodedata.combining(char))
    return stripped.lower()
