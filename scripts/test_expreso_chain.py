"""Simulate orchestrator triple render for expreso."""
import asyncio
from datetime import datetime, timezone

from scraper_agent.parser.article_extractor import article_in_date_range, extract_article
from scraper_agent.parser.html_parser import is_cloudflare_challenge
from scraper_agent.renderer.playwright_renderer import PlaywrightRenderer

URL = "https://www.expreso.com.pe/judicial/caso-gasoducto-sur-pj-archiva-acusacion-por-asociacion-ilicita-contra-ollanta-humala-nadine-heredia-y-otros-estado-noticia/1299285"


async def render_chain(renderer: PlaywrightRenderer, url: str) -> str:
    html = await renderer.render(url, wait_until="load")
    if is_cloudflare_challenge(html):
        print("retry 1")
        await asyncio.sleep(3)
        html = await renderer.render(url, wait_until="load")
    if is_cloudflare_challenge(html):
        print("still cf after retry 1")
    return html


async def main() -> None:
    r = PlaywrightRenderer()
    await r.start()
    # warm like crawl: robots + home
    await r.render("https://www.expreso.com.pe/robots.txt")
    await r.render("https://www.expreso.com.pe/")
    html = await render_chain(r, URL)
    if is_cloudflare_challenge(html):
        print("block path")
        html = await render_chain(r, URL)
    art = extract_article(URL, html, 200, datetime.now(timezone.utc), site_name="expreso.com.pe")
    print("cf final", is_cloudflare_challenge(html), "len", len(html))
    print("dates", (art or {}).get("dates"))
    df = datetime.fromisoformat("2026-07-01T05:00:00+00:00")
    dt = datetime.fromisoformat("2026-07-06T04:59:59+00:00")
    if art:
        print("in_range", article_in_date_range(art, df, dt))
    await r.stop()


if __name__ == "__main__":
    asyncio.run(main())
