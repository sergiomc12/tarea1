"""Tests de fingerprint y headers anti-bot."""

from scraper_agent.anti_detection.fingerprint import (
    chrome_client_hints,
    resolve_fetch_site,
)
from scraper_agent.fetcher.headers import build_headers

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def test_chrome_client_hints_from_user_agent():
    hints = chrome_client_hints(CHROME_UA)
    assert "Sec-CH-UA" in hints
    assert "124" in hints["Sec-CH-UA"]
    assert hints["Sec-CH-UA-Platform"] == '"Windows"'


def test_build_headers_includes_sec_fetch_and_client_hints():
    headers = build_headers(user_agent=CHROME_UA, url="https://peru21.pe/nota/", referer="https://peru21.pe/")
    assert headers["Sec-Fetch-Site"] == "same-origin"
    assert "Sec-CH-UA" in headers
    assert headers["Accept-Language"].startswith("es-PE")


def test_resolve_fetch_site_cross_site():
    assert resolve_fetch_site("https://peru21.pe/rss", "https://google.com/") == "cross-site"
