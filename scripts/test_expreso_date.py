"""Debug expreso date filter on crawl URLs."""
import asyncio
from datetime import datetime, timezone

from scraper_agent.parser.article_extractor import article_in_date_range, extract_article
from scraper_agent.parser.html_parser import is_cloudflare_challenge
from scraper_agent.renderer.playwright_renderer import PlaywrightRenderer

URL = "https://www.expreso.com.pe/judicial/caso-gasoducto-sur-pj-archiva-acusacion-por-asociacion-ilicita-contra-ollanta-humala-nadine-heredia-y-otros-estado-noticia/1299285"


async def main() -> None:
    r = PlaywrightRenderer()
    await r.start()
    html = await r.render(URL, wait_until="load")
    await r.stop()
    print("cf?", is_cloudflare_challenge(html), "len", len(html))
    art = extract_article(URL, html, 200, datetime.now(timezone.utc), site_name="expreso.com.pe")
    print("art", art is not None)
    if art:
        print("dates", art.get("dates"))
        df = datetime.fromisoformat("2026-07-01T05:00:00+00:00")
        dt = datetime.fromisoformat("2026-07-06T04:59:59+00:00")
        print("in_range", article_in_date_range(art, df, dt))


if __name__ == "__main__":
    asyncio.run(main())
