"""Deduplicación de registros."""

import hashlib
from typing import Any


class Deduplicator:
    """Evita duplicados por hash de contenido o clave."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def _hash(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def is_duplicate(self, url: str, data: dict[str, Any]) -> bool:
        """True si ya se procesó un registro equivalente."""
        payload = url + "|" + str(sorted(data.items()))
        digest = self._hash(payload)
        if digest in self._seen:
            return True
        self._seen.add(digest)
        return False

    def reset(self) -> None:
        self._seen.clear()
