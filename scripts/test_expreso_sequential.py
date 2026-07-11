"""Home new page close, then article new page, same context."""
import asyncio
from datetime import datetime, timezone

from scraper_agent.parser.article_extractor import article_in_date_range, extract_article
from scraper_agent.parser.html_parser import is_cloudflare_challenge
from scraper_agent.renderer.playwright_renderer import PlaywrightRenderer

HOME = "https://www.expreso.com.pe/"
ARTICLE = "https://www.expreso.com.pe/actualidad/temblor-hoy-5-de-julio-de-2026-en-ica-epicentro-magnitud-y-reporte-oficial-del-igp-hace-minutos-instituto-geofisico-del-peru-terremoto-sismo-indeci-emergencia-noticia/1299300"


async def main() -> None:
    r = PlaywrightRenderer()
    await r.start()
    home = await r.render(HOME, wait_until="load")
    print("home", not is_cloudflare_challenge(home), len(home))
    await asyncio.sleep(3)
    html = await r.render(ARTICLE, wait_until="load")
    print("article cf?", is_cloudflare_challenge(html), "len", len(html))
    art = extract_article(ARTICLE, html, 200, datetime.now(timezone.utc), site_name="expreso.com.pe")
    if art:
        print("dates", art.get("dates"))
        df = datetime.fromisoformat("2026-07-01T05:00:00+00:00")
        dt = datetime.fromisoformat("2026-07-06T04:59:59+00:00")
        print("in_range", article_in_date_range(art, df, dt))
    await r.stop()


if __name__ == "__main__":
    asyncio.run(main())
