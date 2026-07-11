"""Coherencia de fingerprint HTTP tipo navegador Chrome."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from scraper_agent.anti_detection.user_agents import pick_user_agent


def _chrome_version(user_agent: str) -> str:
    match = re.search(r"Chrome/(\d+)", user_agent)
    return match.group(1) if match else "124"


def _platform_hint(user_agent: str) -> str:
    if "Macintosh" in user_agent:
        return "macOS"
    if "Linux" in user_agent:
        return "Linux"
    return "Windows"


def chrome_client_hints(user_agent: str) -> dict[str, str]:
    """Sec-CH-UA alineado al User-Agent (solo Chromium)."""
    if "Chrome/" not in user_agent or "Edg/" in user_agent:
        return {}
    version = _chrome_version(user_agent)
    platform = _platform_hint(user_agent)
    return {
        "Sec-CH-UA": (
            f'"Chromium";v="{version}", "Google Chrome";v="{version}", "Not-A.Brand";v="99"'
        ),
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": f'"{platform}"',
    }


def sec_fetch_headers(*, site: str = "none", dest: str = "document") -> dict[str, str]:
    """Cabeceras Sec-Fetch-* coherentes con una navegación real."""
    return {
        "Sec-Fetch-Dest": dest,
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": site,
        "Sec-Fetch-User": "?1",
    }


def resolve_fetch_site(url: str, referer: str | None) -> str:
    """none | same-origin | cross-site según referer."""
    if not referer:
        return "none"
    ref_host = urlparse(referer).netloc.lower()
    url_host = urlparse(url).netloc.lower()
    if not ref_host or not url_host:
        return "none"
    if ref_host == url_host:
        return "same-origin"
    ref_root = ".".join(ref_host.split(".")[-2:])
    url_root = ".".join(url_host.split(".")[-2:])
    return "same-site" if ref_root == url_root else "cross-site"


def pick_session_user_agent(rotate: bool = True) -> str:
    """UA fijo por sesión de crawl (no rotar en cada request)."""
    return pick_user_agent() if rotate else pick_user_agent()
