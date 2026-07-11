"""Autenticación con usuario/contraseña."""

import os
from urllib.parse import urlparse

import httpx

from scraper_agent.models.schemas import AuthConfig
from scraper_agent.renderer.playwright_renderer import PlaywrightRenderer
from scraper_agent.utils.logger import get_logger

logger = get_logger(__name__)


class LoginManager:
    """Login simple POST o vía Playwright."""

    def __init__(self, config: AuthConfig, client_cookies: httpx.Cookies) -> None:
        self._config = config
        self._cookies = client_cookies
        self._logged_in = False

    def _credentials(self) -> tuple[str, str]:
        user = os.getenv(self._config.username_env, "")
        password = os.getenv(self._config.password_env, "")
        if not user or not password:
            raise ValueError("Credenciales no definidas en variables de entorno")
        return user, password

    async def login_http(self, client: httpx.AsyncClient) -> None:
        """POST form login clásico."""
        username, password = self._credentials()
        login_url = self._config.login_url
        if not login_url:
            raise ValueError("auth.login_url requerido cuando auth.enabled=true")
        response = await client.post(
            login_url,
            data={"username": username, "password": password},
            follow_redirects=True,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Login falló con status {response.status_code}")
        self._cookies.update(response.cookies)
        self._logged_in = True
        logger.info("login_ok", url=login_url)

    async def login_playwright(self, renderer: PlaywrightRenderer, login_url: str) -> None:
        """Login vía formulario JS."""
        username, password = self._credentials()
        if not renderer._context:
            await renderer.start()
        page = await renderer._context.new_page()
        try:
            await page.goto(login_url, wait_until="networkidle")
            await page.fill('input[type="email"], input[name="username"], input[name="user"]', username)
            await page.fill('input[type="password"]', password)
            await page.click('button[type="submit"], input[type="submit"]')
            await page.wait_for_load_state("networkidle")
            cookies = await renderer._context.cookies()
            for c in cookies:
                domain = c.get("domain") or urlparse(login_url).hostname or ""
                self._cookies.set(c["name"], c["value"], domain=domain)
            self._logged_in = True
            logger.info("login_playwright_ok", url=login_url)
        finally:
            await page.close()

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
