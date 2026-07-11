"""Extracción de enlaces desde HTML."""

import re
from urllib.parse import urljoin

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scraper_agent.utils.url_utils import normalize_url, resolve_url

LINK_ATTRS = ("href",)


def extract_links(html: str, base_url: str) -> list[str]:
    """Extrae y normaliza enlaces internos candidatos."""
    soup = BeautifulSoup(html, "lxml")
    found: set[str] = set()
    for tag in soup.find_all(["a", "link", "area"]):
        for attr in LINK_ATTRS:
            href = tag.get(attr)
            resolved = resolve_url(base_url, href) if href else None
            if resolved:
                found.add(resolved)
    return sorted(found)


def extract_sitemap_urls(xml_text: str, base_url: str) -> list[str]:
    """Extrae URLs de un sitemap XML simple."""
    urls: list[str] = []
    for match in re.finditer(r"<loc>\s*(.*?)\s*</loc>", xml_text, re.I):
        loc = match.group(1).strip()
        if loc:
            urls.append(normalize_url(urljoin(base_url, loc)))
    return urls


def is_sitemap_document(url: str, content: str) -> bool:
    """True si la respuesta parece un sitemap XML (índice o urlset)."""
    path = urlparse(url).path.lower()
    if path.endswith(".xml") or "sitemap" in path:
        return True
    snippet = (content or "")[:800].lower()
    return "<urlset" in snippet or "<sitemapindex" in snippet


def is_nested_sitemap_url(url: str) -> bool:
    """True si la URL apunta a otro sitemap hijo."""
    path = urlparse(url).path.lower()
    return path.endswith(".xml") or "/sitemap" in path
