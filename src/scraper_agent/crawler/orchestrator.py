"""Orquestador principal del crawl BFS."""

import asyncio
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from urllib.robotparser import RobotFileParser

from scraper_agent.auth.login_manager import LoginManager
from scraper_agent.crawler.scope import CrawlScope
from scraper_agent.crawler.url_frontier import UrlFrontier
from scraper_agent.fetcher.http_client import FetchResponse, HttpClient
from scraper_agent.fetcher.proxy_manager import ProxyManager
from scraper_agent.fetcher.rate_limiter import DomainRateLimiter
from scraper_agent.models.schemas import AppConfig, CrawlRunSummary
from scraper_agent.parser.article_extractor import article_in_date_range, extract_article
from scraper_agent.parser.html_parser import is_cloudflare_challenge, needs_js_render
from scraper_agent.parser.link_extractor import (
    extract_links,
    extract_sitemap_urls,
    is_nested_sitemap_url,
    is_sitemap_document,
)
from scraper_agent.parser.rss_feed import parse_rss_feed
from scraper_agent.renderer.playwright_renderer import PlaywrightRenderer
from scraper_agent.storage.json_writer import JsonWriter
from scraper_agent.storage.schema_validator import validate_article
from scraper_agent.utils.logger import get_logger
from scraper_agent.utils.url_utils import normalize_url, registrable_domain

logger = get_logger(__name__)


def _parse_cli_date(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _make_crawl_id(domain: str, started: datetime) -> str:
    host = registrable_domain(domain).split(".")[0]
    return f"{host}-{started.strftime('%Y%m%d-%H%M%S')}"


class CrawlOrchestrator:
    """Coordina fetch, extracción de artículos y persistencia."""

    def __init__(
        self,
        config: AppConfig,
        ignore_robots: bool = False,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> None:
        self._config = config
        self._ignore_robots = ignore_robots
        self._date_from = date_from
        self._date_to = date_to
        if not date_from and config.date_range:
            self._date_from = _parse_cli_date(config.date_range.from_date)
            self._date_to = _parse_cli_date(config.date_range.to_date)
        self._seed = normalize_url(config.domain)
        self._scope = CrawlScope(
            self._seed,
            include_subdomains=config.scope.include_subdomains,
            max_depth=config.scope.max_depth,
            exclude_patterns=config.scope.exclude_patterns,
        )
        self._writer = JsonWriter(
            config.output.path,
            config.output.checkpoint_dir,
            incremental=config.output.incremental,
            use_jsonl=config.output.format.lower() == "jsonl",
        )
        self._robots: RobotFileParser | None = None
        self._robots_respected = config.respect_robots_txt and not ignore_robots
        self._errors: list[dict] = []
        self._discovery_mode = (config.discovery.mode or "crawl").lower()
        self._follow_page_links = self._discovery_mode != "rss" and not config.discovery.article_link_pattern
        self._renderer: PlaywrightRenderer | None = None

    async def _ensure_renderer(self, client: HttpClient) -> PlaywrightRenderer | None:
        if self._renderer is not None:
            return self._renderer
        try:
            self._renderer = PlaywrightRenderer(user_agent=client.user_agent)
            await self._renderer.start()
            return self._renderer
        except Exception as exc:
            logger.warning("playwright_unavailable", error=str(exc)[:200])
            self._renderer = None
            return None

    async def _reset_renderer(self) -> None:
        if self._renderer:
            await self._renderer.stop()
            self._renderer = None

    async def _render_with_playwright(
        self,
        url: str,
        client: HttpClient,
        *,
        reason: str,
        referer: str | None = None,
        wait_until: str = "load",
        fresh_browser: bool = False,
    ) -> FetchResponse | None:
        if fresh_browser:
            await self._reset_renderer()
        renderer = await self._ensure_renderer(client)
        if renderer is None:
            return None
        logger.info(reason, url=url)
        ref = referer or self._seed
        use_pw = self._config.anti_detection.prefer_playwright
        is_home = normalize_url(url) == self._seed
        try:
            if use_pw and not is_home:
                html = await renderer.render(url, wait_until=wait_until)
            elif use_pw and is_home:
                html = await renderer.render_persistent(url, referer=ref, wait_until=wait_until)
            else:
                html = await renderer.render(url, wait_until=wait_until)
            if is_cloudflare_challenge(html):
                logger.info("playwright_cloudflare_retry", url=url)
                await asyncio.sleep(3)
                await self._reset_renderer()
                renderer = await self._ensure_renderer(client)
                if renderer is None:
                    return None
                html = await renderer.render(url, wait_until="load")
            if is_cloudflare_challenge(html):
                logger.warning("playwright_still_cloudflare", url=url)
                return None
        except Exception as exc:
            logger.warning("playwright_render_failed", url=url, error=str(exc)[:200])
            return None
        if use_pw and not is_home:
            lo, hi = self._config.anti_detection.random_delay_range
            await asyncio.sleep(lo + (hi - lo) * 0.5)
        return FetchResponse(url=url, status_code=200, text=html, headers={})

    async def _fetch_url(
        self,
        url: str,
        client: HttpClient,
        referer: str | None = None,
    ) -> FetchResponse:
        """GET con fallback Playwright ante HTTP 403 o prefer_playwright."""
        ad = self._config.anti_detection
        ref = referer or self._seed
        if ad.prefer_playwright:
            rendered = await self._render_with_playwright(
                url,
                client,
                reason="playwright_preferred",
                referer=ref,
                fresh_browser=normalize_url(url) != self._seed,
            )
            if rendered is not None:
                return rendered
            return FetchResponse(url=url, status_code=403, text="", headers={})

        resp = await client.fetch(url, referer=ref)
        if resp.status_code != 403 or not ad.use_playwright_on_403:
            return resp
        rendered = await self._render_with_playwright(
            url, client, reason="playwright_fallback_403", referer=ref
        )
        return rendered if rendered is not None else resp

    async def _seed_rss_feeds(self, client: HttpClient, frontier: UrlFrontier) -> int:
        """Carga URLs de noticias desde feeds RSS/Atom configurados."""
        feeds = self._config.discovery.rss_feeds
        if not feeds or self._discovery_mode not in ("rss", "both"):
            return 0
        max_items = self._config.discovery.max_items_per_feed
        added = 0
        for feed_url in feeds:
            feed_added = 0
            try:
                resp = await self._fetch_url(feed_url, client)
                if resp.status_code != 200 or not resp.text:
                    logger.warning("rss_feed_failed", feed=feed_url, status=resp.status_code)
                    continue
                items = parse_rss_feed(resp.text)
                if max_items > 0:
                    items = items[:max_items]
                for item in items:
                    url = item["url"]
                    if self._scope.is_allowed(url) and frontier.enqueue_priority(url):
                        feed_added += 1
                added += feed_added
                logger.info("rss_feed_loaded", feed=feed_url, items=len(items), enqueued=feed_added)
            except Exception as exc:
                logger.warning("rss_feed_error", feed=feed_url, error=str(exc))
        return added

    async def _seed_playwright_home(self, client: HttpClient, frontier: UrlFrontier) -> int:
        """Encola enlaces de artículos desde la home vía Playwright (sitios con CF)."""
        pattern_text = self._config.discovery.article_link_pattern
        if not pattern_text or not self._config.anti_detection.prefer_playwright:
            return 0
        resp = await self._render_with_playwright(self._seed, client, reason="playwright_home_seed")
        if resp is None or not resp.text:
            return 0
        link_re = re.compile(pattern_text, re.I)
        max_items = self._config.discovery.max_items_per_feed
        added = 0
        for link in extract_links(resp.text, self._seed):
            if max_items > 0 and added >= max_items:
                break
            if link_re.search(link) and self._scope.is_allowed(link):
                if frontier.enqueue_priority(link):
                    added += 1
        await self._reset_renderer()
        logger.info("playwright_home_seeded", enqueued=added)
        return added

    async def _expand_sitemaps(
        self,
        client: HttpClient,
        frontier: UrlFrontier,
        *,
        extra_sitemaps: list[str] | None = None,
        max_fetches: int = 25,
    ) -> None:
        """Resuelve sitemap índice y encola URLs de artículos (no XML hijos como páginas)."""
        pending: list[str] = [urljoin(self._seed, "/sitemap.xml")]
        if extra_sitemaps:
            pending.extend(extra_sitemaps)
        seen: set[str] = set()
        fetched = 0
        while pending and fetched < max_fetches:
            sm_url = pending.pop(0)
            if sm_url in seen:
                continue
            seen.add(sm_url)
            try:
                resp = await self._fetch_url(sm_url, client)
            except Exception:
                continue
            fetched += 1
            if resp.status_code != 200 or not resp.text:
                continue
            if not is_sitemap_document(sm_url, resp.text):
                continue
            for loc in extract_sitemap_urls(resp.text, self._seed):
                if is_nested_sitemap_url(loc):
                    if loc not in seen:
                        pending.append(loc)
                elif self._scope.is_allowed(loc):
                    frontier.enqueue(loc)

    async def _load_robots(self, client: HttpClient) -> None:
        if not self._robots_respected:
            return
        robots_url = urljoin(self._seed, "/robots.txt")
        try:
            resp = await self._fetch_url(robots_url, client)
            if resp.status_code == 200:
                rp = RobotFileParser()
                rp.parse(resp.text.splitlines())
                self._robots = rp
                logger.info("robots_loaded", url=robots_url)
        except Exception as exc:
            logger.warning("robots_unavailable", error=str(exc))

    def _can_fetch(self, url: str) -> bool:
        if not self._robots_respected or not self._robots:
            return True
        return self._robots.can_fetch("*", url)

    async def _maybe_render(
        self,
        url: str,
        html: str,
        client: HttpClient,
    ) -> str:
        mode = self._config.render.mode.lower()
        if mode == "never":
            return html
        if mode == "always" or (mode == "auto" and needs_js_render(html)):
            renderer = await self._ensure_renderer(client)
            if renderer is None:
                return html
            logger.info("render_js", url=url)
            return await renderer.render(url)
        return html

    async def _process_url(
        self,
        url: str,
        client: HttpClient,
        referer: str | None,
        fetched_at: datetime,
    ) -> list[str]:
        if not self._can_fetch(url):
            logger.info("robots_blocked", url=url)
            return []
        try:
            resp = await self._fetch_url(url, client, referer=referer)
        except Exception as exc:
            logger.error("fetch_failed", url=url, error=str(exc))
            self._errors.append(
                {
                    "url": url,
                    "error_type": "unknown",
                    "message": str(exc),
                    "status_code": None,
                    "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            )
            self._writer.record_page_visit()
            return []

        html = resp.text
        self._writer.record_page_visit()

        if resp.status_code != 200 or not html:
            return []

        if is_cloudflare_challenge(html):
            logger.warning("cloudflare_page_skip", url=url)
            return []

        if not self._config.anti_detection.prefer_playwright:
            html = await self._maybe_render(url, html, client)
            if is_cloudflare_challenge(html):
                logger.warning("cloudflare_page_skip", url=url)
                return []

        if is_sitemap_document(url, html):
            links: list[str] = []
            for loc in extract_sitemap_urls(html, url):
                if is_nested_sitemap_url(loc) or self._scope.is_allowed(loc):
                    links.append(loc)
            return links if self._follow_page_links else []

        links = extract_links(html, url) if html else []

        article = extract_article(
            url,
            html,
            resp.status_code,
            fetched_at,
            site_name=registrable_domain(self._seed),
        )
        if article is None:
            return links if self._follow_page_links else []

        if not article_in_date_range(article, self._date_from, self._date_to):
            logger.info("article_filtered_by_date", url=url)
            return links if self._follow_page_links else []

        article_errors = validate_article(article)
        if article_errors:
            logger.warning(
                "article_schema_rejected",
                url=url,
                errors=article_errors[:3],
            )
            return links if self._follow_page_links else []

        self._writer.append_article(article)
        return links if self._follow_page_links else []

    async def run(self) -> CrawlRunSummary:
        """Ejecuta el crawl completo."""
        started = datetime.now(timezone.utc)
        crawl_id = _make_crawl_id(self._seed, started)
        visited, pending = self._writer.load_checkpoint()
        seed_queue = (
            self._discovery_mode != "rss"
            and not self._config.discovery.article_link_pattern
        )
        frontier = UrlFrontier(
            self._seed,
            visited=visited,
            pending=pending or None,
            seed_queue=seed_queue,
        )

        rate = DomainRateLimiter(self._config.concurrency.requests_per_second_per_domain)
        proxy_mgr = ProxyManager(self._config.anti_detection.proxies_env)
        ad = self._config.anti_detection

        sem = asyncio.Semaphore(self._config.concurrency.max_workers)
        pages_done = 0
        lock = asyncio.Lock()
        user_agent = ""

        async with HttpClient(
            rate_limiter=rate,
            proxy_manager=proxy_mgr,
            rotate_user_agent=ad.rotate_user_agent,
            delay_range=tuple(ad.random_delay_range),
            max_attempts=self._config.retry.max_attempts,
            chrome_client_hints=ad.chrome_client_hints,
        ) as client:
            user_agent = client.user_agent
            if ad.prefer_playwright:
                pass
            elif ad.session_warmup:
                await client.warmup(self._seed)
            if not ad.prefer_playwright:
                await self._load_robots(client)

            if self._config.auth.enabled:
                login = LoginManager(self._config.auth, client.cookies)
                if self._config.render.mode == "always":
                    await self._ensure_renderer(client)
                    await login.login_playwright(self._renderer, self._config.auth.login_url)
                else:
                    import httpx

                    async with httpx.AsyncClient(cookies=client.cookies, follow_redirects=True) as raw:
                        await login.login_http(raw)

            try:
                if self._discovery_mode != "rss" and self._config.discovery.expand_sitemaps:
                    await self._expand_sitemaps(
                        client,
                        frontier,
                        extra_sitemaps=self._config.discovery.sitemap_urls or None,
                    )
            except Exception:
                pass

            await self._seed_rss_feeds(client, frontier)
            await self._seed_playwright_home(client, frontier)

            async def handle_url(url: str) -> None:
                nonlocal pages_done
                if not self._scope.is_allowed(url):
                    return
                async with sem:
                    links = await self._process_url(url, client, self._seed, datetime.now(timezone.utc))
                async with lock:
                    pages_done += 1
                    for link in links:
                        if self._scope.is_allowed(link):
                            frontier.enqueue(link)
                    vis, pend = frontier.snapshot()
                    self._writer.save_checkpoint(vis, pend)

            while not frontier.is_empty() and pages_done < self._config.scope.max_pages:
                batch: list[str] = []
                async with lock:
                    while not frontier.is_empty() and len(batch) < self._config.concurrency.max_workers:
                        if pages_done + len(batch) >= self._config.scope.max_pages:
                            break
                        next_url = frontier.dequeue()
                        if next_url is None:
                            break
                        if frontier.was_visited(next_url):
                            continue
                        frontier.mark_visited(next_url)
                        batch.append(next_url)
                if not batch:
                    break
                await asyncio.gather(*(handle_url(u) for u in batch))

        if self._renderer:
            await self._renderer.stop()
            self._renderer = None

        date_filter = None
        if self._date_from or self._date_to:
            date_filter = {
                "from": self._date_from.isoformat().replace("+00:00", "Z") if self._date_from else None,
                "to": self._date_to.isoformat().replace("+00:00", "Z") if self._date_to else None,
            }

        self._writer.write_final(
            crawl_id=crawl_id,
            domain=registrable_domain(self._seed),
            started_at=started,
            robots_txt_respected=self._robots_respected,
            date_range_filter=date_filter,
            user_agent=user_agent,
            errors=self._errors,
        )

        return CrawlRunSummary(
            crawl_id=crawl_id,
            domain=registrable_domain(self._seed),
            total_pages_visited=pages_done,
            total_articles_extracted=self._writer.article_count,
            crawl_started_at=started,
            crawl_finished_at=datetime.now(timezone.utc),
            robots_txt_respected=self._robots_respected,
        )
