"""Reglas de alcance del crawl."""

import re
from urllib.parse import urlparse

from scraper_agent.utils.url_utils import is_same_registrable_domain, path_depth


class CrawlScope:
    """Determina si una URL está dentro del alcance."""

    def __init__(
        self,
        seed_url: str,
        include_subdomains: bool = True,
        max_depth: int = 6,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        parsed = urlparse(seed_url)
        self.root_url = seed_url.rstrip("/") if seed_url.endswith("/") else seed_url
        self.root_domain = parsed.netloc.lower()
        self.include_subdomains = include_subdomains
        self.max_depth = max_depth
        self._exclude = [re.compile(p, re.I) for p in (exclude_patterns or [])]

    def is_allowed(self, url: str) -> bool:
        """True si la URL puede crawlearse."""
        if not is_same_registrable_domain(url, self.root_domain, self.include_subdomains):
            return False
        path = urlparse(url).path or "/"
        for pattern in self._exclude:
            if pattern.search(path) or pattern.search(url):
                return False
        depth = path_depth(url, self.root_url)
        if depth > self.max_depth:
            return False
        return True
