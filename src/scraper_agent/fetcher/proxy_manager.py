"""Rotación de proxies desde variable de entorno."""

import os
import random
from itertools import cycle
from typing import Iterator


class ProxyManager:
    """Pool de proxies con rotación round-robin o aleatoria."""

    def __init__(self, env_var: str = "PROXY_LIST") -> None:
        raw = os.getenv(env_var, "").strip()
        self._proxies: list[str] = [p.strip() for p in raw.split(",") if p.strip()]
        self._cycle: Iterator[str] | None = cycle(self._proxies) if self._proxies else None
        self._failed: set[str] = set()

    @property
    def has_proxies(self) -> bool:
        return bool(self._proxies)

    def next_proxy(self, random_pick: bool = False) -> str | None:
        """Obtiene el siguiente proxy disponible."""
        available = [p for p in self._proxies if p not in self._failed]
        if not available:
            return None
        if random_pick:
            return random.choice(available)
        if self._cycle is None:
            return None
        for _ in range(len(self._proxies)):
            proxy = next(self._cycle)
            if proxy not in self._failed:
                return proxy
        return None

    def mark_failed(self, proxy: str) -> None:
        """Marca un proxy como caído."""
        self._failed.add(proxy)
