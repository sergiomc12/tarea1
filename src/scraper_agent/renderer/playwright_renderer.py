"""Renderizado JS con Playwright (opcional)."""

from scraper_agent.anti_detection.user_agents import pick_user_agent
from scraper_agent.utils.logger import get_logger

logger = get_logger(__name__)


class PlaywrightRenderer:
    """Render headless Chromium async con contexto realista."""

    def __init__(self, user_agent: str | None = None) -> None:
        self._user_agent = user_agent or pick_user_agent()
        self._playwright = None
        self._browser = None
        self._context = None
        self._persistent_page = None

    async def start(self) -> None:
        """Inicia browser y contexto compartido."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            user_agent=self._user_agent,
            locale="es-PE",
            timezone_id="America/Lima",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={
                "Accept-Language": "es-PE,es;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

    async def stop(self) -> None:
        """Cierra recursos."""
        if self._persistent_page and not self._persistent_page.is_closed():
            await self._persistent_page.close()
        self._persistent_page = None
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._context = None
        self._browser = None
        self._playwright = None

    async def _ensure_persistent_page(self):
        if not self._context:
            raise RuntimeError("PlaywrightRenderer no iniciado")
        if self._persistent_page is None or self._persistent_page.is_closed():
            self._persistent_page = await self._context.new_page()
        return self._persistent_page

    async def _wait_cloudflare(self, page) -> None:
        """Espera a que termine un challenge de Cloudflare (si aplica)."""
        try:
            await page.wait_for_function(
                """() => {
                    const title = (document.title || '').toLowerCase();
                    if (title.includes('moment') || title.includes('momento')) return false;
                    if (title.includes('attention required')) return false;
                    if (document.querySelector('#challenge-running, #cf-challenge-running')) {
                        return false;
                    }
                    return document.body && document.body.innerText.length > 400;
                }""",
                timeout=45000,
            )
        except Exception:
            await page.wait_for_timeout(5000)

    async def fetch_with_context(
        self,
        url: str,
        *,
        referer: str | None = None,
    ) -> str:
        """GET con cookies del contexto (evita nuevo challenge CF por navegación)."""
        if not self._context:
            raise RuntimeError("PlaywrightRenderer no iniciado")
        headers: dict[str, str] = {}
        if referer:
            headers["Referer"] = referer
        response = await self._context.request.get(url, headers=headers or None, timeout=90000)
        if response.status >= 400:
            logger.warning("context_request_failed", url=url, status=response.status)
        return await response.text()

    async def render_persistent(
        self,
        url: str,
        *,
        referer: str | None = None,
        wait_until: str = "load",
        cloudflare_wait: bool = True,
    ) -> str:
        """Navega reutilizando la misma pestaña (conserva cookies CF)."""
        page = await self._ensure_persistent_page()
        await page.goto(
            url,
            wait_until=wait_until,
            timeout=90000,
            referer=referer,
        )
        if cloudflare_wait:
            await self._wait_cloudflare(page)
        return await page.content()

    async def render(
        self,
        url: str,
        wait_selector: str | None = None,
        *,
        wait_until: str = "domcontentloaded",
        cloudflare_wait: bool = True,
    ) -> str:
        """Navega a URL y devuelve HTML renderizado."""
        if not self._context:
            raise RuntimeError("PlaywrightRenderer no iniciado")
        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until=wait_until, timeout=90000)
            if cloudflare_wait:
                await self._wait_cloudflare(page)
            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=15000)
            return await page.content()
        finally:
            await page.close()
