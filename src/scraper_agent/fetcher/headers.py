"""Construcción de headers HTTP."""

from scraper_agent.anti_detection.fingerprint import (
    chrome_client_hints,
    resolve_fetch_site,
    sec_fetch_headers,
)
from scraper_agent.anti_detection.user_agents import pick_user_agent


def build_headers(
    user_agent: str | None = None,
    referer: str | None = None,
    *,
    url: str | None = None,
    chrome_client_hints_enabled: bool = True,
) -> dict[str, str]:
    """Construye headers realistas para una petición."""
    ua = user_agent or pick_user_agent()
    fetch_site = resolve_fetch_site(url or referer or "", referer) if url or referer else "none"
    headers = {
        "User-Agent": ua,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "es-PE,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        **sec_fetch_headers(site=fetch_site),
    }
    if chrome_client_hints_enabled:
        headers.update(chrome_client_hints(ua))
    if referer:
        headers["Referer"] = referer
    return headers
