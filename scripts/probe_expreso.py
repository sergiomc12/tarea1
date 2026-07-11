"""Probe expreso.com.pe discovery options."""
import asyncio
import re

from scraper_agent.parser.link_extractor import extract_links, extract_sitemap_urls, is_sitemap_document
from scraper_agent.parser.rss_feed import normalize_feed_xml, parse_rss_feed
from scraper_agent.renderer.playwright_renderer import PlaywrightRenderer


async def wait_cloudflare(page, timeout_ms: int = 45000) -> None:
    """Espera a que pase el challenge de Cloudflare."""
    try:
        await page.wait_for_function(
            """() => {
                const t = document.title.toLowerCase();
                if (t.includes('moment') || t.includes('momento') || t.includes('just a')) return false;
                if (document.querySelector('#challenge-running, #cf-challenge-running')) return false;
                return document.body && document.body.innerText.length > 500;
            }""",
            timeout=timeout_ms,
        )
    except Exception:
        await page.wait_for_timeout(8000)


async def fetch(renderer: PlaywrightRenderer, url: str) -> str:
    page = await renderer._context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=90000)
        await wait_cloudflare(page)
        return await page.content()
    finally:
        await page.close()


async def main() -> None:
    renderer = PlaywrightRenderer()
    await renderer.start()
    urls = [
        "https://www.expreso.com.pe/",
        "https://www.expreso.com.pe/feed/",
        "https://www.expreso.com.pe/sitemap.xml",
        "https://www.expreso.com.pe/sitemap_index.xml",
        "https://www.expreso.com.pe/wp-sitemap.xml",
        "https://www.expreso.com.pe/noticias/",
    ]
    for url in urls:
        html = await fetch(renderer, url)
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title = title_m.group(1)[:80] if title_m else "?"
        print(f"\n=== {url} ===")
        print("title:", title, "len:", len(html))
        if "feed" in url:
            norm = normalize_feed_xml(html)
            print("feed items:", len(parse_rss_feed(html)), "norm starts:", norm[:120])
        if is_sitemap_document(url, html):
            locs = extract_sitemap_urls(html, url)[:5]
            print("sitemap locs sample:", locs)
        links = extract_links(html, url)
        articleish = [u for u in links if re.search(r"/\d{4}/|/noticia", u)][:8]
        print("article links:", len(articleish), articleish[:5])
    await renderer.stop()


if __name__ == "__main__":
    asyncio.run(main())
