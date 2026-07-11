"""Test expreso article extraction."""
import asyncio

from scraper_agent.renderer.playwright_renderer import PlaywrightRenderer
from scraper_agent.parser.article_extractor import article_in_date_range, extract_article
from datetime import datetime, timezone


async def main() -> None:
    url = "https://www.expreso.com.pe/actualidad/temblor-hoy-5-de-julio-de-2026-en-ica-epicentro-magnitud-y-reporte-oficial-del-igp-hace-minutos-instituto-geofisico-del-peru-terremoto-sismo-indeci-emergencia-noticia/1299300"
    r = PlaywrightRenderer()
    await r.start()
    html = await r.render(url, wait_until="load")
    await r.stop()
    from datetime import datetime, timezone

    fetched = datetime.now(timezone.utc)
    art = extract_article(url, html, 200, fetched, site_name="expreso.com.pe")
    print("article?", art is not None)
    if art:
        print("title", art.get("title"))
        print("dates", art.get("dates"))
        print("blocks", len(art.get("content_blocks") or []))
        df = datetime.fromisoformat("2026-07-01T05:00:00+00:00")
        dt = datetime.fromisoformat("2026-07-06T04:59:59+00:00")
        print("in_range", article_in_date_range(art, df, dt))


if __name__ == "__main__":
    asyncio.run(main())
