"""Tests del fetcher."""

import httpx
import pytest
import respx

from scraper_agent.fetcher.headers import build_headers
from scraper_agent.fetcher.http_client import HttpClient
from scraper_agent.fetcher.proxy_manager import ProxyManager
from scraper_agent.fetcher.rate_limiter import DomainRateLimiter
from scraper_agent.fetcher.retry import is_retryable_status


def test_build_headers_includes_user_agent():
    headers = build_headers()
    assert "User-Agent" in headers
    assert headers["Accept-Language"].startswith("es")


def test_is_retryable_status():
    assert is_retryable_status(429) is True
    assert is_retryable_status(503) is True
    assert is_retryable_status(404) is False


def test_proxy_manager_rotation():
    import os

    os.environ["PROXY_LIST"] = "http://a:1,http://b:2"
    mgr = ProxyManager("PROXY_LIST")
    assert mgr.has_proxies
    p1 = mgr.next_proxy()
    p2 = mgr.next_proxy()
    assert p1 in ("http://a:1", "http://b:2")
    assert p2 in ("http://a:1", "http://b:2")


@pytest.mark.asyncio
@respx.mock
async def test_http_client_fetch_ok():
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text="<html>ok</html>"))
    limiter = DomainRateLimiter(10.0)
    async with HttpClient(rate_limiter=limiter, delay_range=(0, 0)) as client:
        resp = await client.fetch("https://example.com")
    assert resp.status_code == 200
    assert "ok" in resp.text
