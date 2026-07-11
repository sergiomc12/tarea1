"""Cliente HTTP async con rate limit, headers y proxies."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from scraper_agent.anti_detection.delays import random_delay
from scraper_agent.anti_detection.fingerprint import pick_session_user_agent
from scraper_agent.fetcher.headers import build_headers
from scraper_agent.fetcher.proxy_manager import ProxyManager
from scraper_agent.fetcher.rate_limiter import DomainRateLimiter
from scraper_agent.fetcher.retry import is_retryable_status
from scraper_agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FetchResponse:
    """Respuesta de una petición HTTP."""

    url: str
    status_code: int
    text: str
    headers: dict[str, str]


class HttpClient:
    """Cliente httpx reutilizable con anti-detección básica."""

    def __init__(
        self,
        rate_limiter: DomainRateLimiter,
        proxy_manager: ProxyManager | None = None,
        timeout: float = 30.0,
        rotate_user_agent: bool = True,
        delay_range: tuple[float, float] = (0.0, 0.0),
        max_attempts: int = 3,
        cookies: httpx.Cookies | None = None,
        chrome_client_hints: bool = True,
        session_user_agent: str | None = None,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._proxy_manager = proxy_manager or ProxyManager()
        self._timeout = timeout
        self._rotate_user_agent = rotate_user_agent
        self._delay_range = delay_range
        self._max_attempts = max_attempts
        self._cookies = cookies or httpx.Cookies()
        self._chrome_client_hints = chrome_client_hints
        self._user_agent = session_user_agent or pick_session_user_agent(rotate_user_agent)
        self._client: httpx.AsyncClient | None = None
        self._warmed_up = False

    async def __aenter__(self) -> "HttpClient":
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            cookies=self._cookies,
            follow_redirects=True,
            http2=True,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def cookies(self) -> httpx.Cookies:
        return self._cookies

    @property
    def user_agent(self) -> str:
        return self._user_agent

    def _build_request_headers(self, url: str, referer: str | None) -> dict[str, str]:
        return build_headers(
            user_agent=self._user_agent,
            referer=referer,
            url=url,
            chrome_client_hints_enabled=self._chrome_client_hints,
        )

    async def warmup(self, url: str) -> int:
        """Visita la home del sitio para obtener cookies de sesión."""
        if self._warmed_up:
            return 200
        resp = await self.fetch(url, referer=None)
        self._warmed_up = True
        logger.info("session_warmup", url=url, status=resp.status_code)
        return resp.status_code

    async def fetch(self, url: str, referer: str | None = None) -> FetchResponse:
        """GET con rate limit, delay, retry manual y rotación de proxy."""
        if not self._client:
            raise RuntimeError("HttpClient no iniciado; usar async with")

        await self._rate_limiter.acquire()
        if self._delay_range[1] > 0:
            await random_delay(self._delay_range[0], self._delay_range[1])

        headers = self._build_request_headers(url, referer)
        last_error: Exception | None = None
        last_status = 0

        for attempt in range(1, self._max_attempts + 1):
            proxy = self._proxy_manager.next_proxy() if self._proxy_manager.has_proxies else None
            try:
                if proxy:
                    async with httpx.AsyncClient(
                        timeout=self._timeout,
                        cookies=self._cookies,
                        follow_redirects=True,
                        proxy=proxy,
                        http2=True,
                    ) as proxied:
                        response = await proxied.get(url, headers=headers)
                else:
                    response = await self._client.get(url, headers=headers)
                last_status = response.status_code
                if response.status_code == 403 and attempt < self._max_attempts:
                    logger.warning("retry_403", url=url, attempt=attempt)
                    await asyncio.sleep(2**attempt)
                    continue
                if is_retryable_status(response.status_code) and attempt < self._max_attempts:
                    logger.warning("retry_status", url=url, status=response.status_code, attempt=attempt)
                    await asyncio.sleep(2**attempt)
                    continue
                return FetchResponse(
                    url=str(response.url),
                    status_code=response.status_code,
                    text=response.text,
                    headers=dict(response.headers),
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if proxy:
                    self._proxy_manager.mark_failed(proxy)
                logger.warning("fetch_error", url=url, attempt=attempt, error=str(exc))
                if attempt >= self._max_attempts:
                    break
                await asyncio.sleep(2**attempt)

        if last_error:
            raise last_error
        if last_status:
            return FetchResponse(url=url, status_code=last_status, text="", headers={})
        raise RuntimeError(f"No se pudo obtener {url}")
