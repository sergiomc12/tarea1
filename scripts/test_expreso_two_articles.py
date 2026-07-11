"""Two articles without home visit."""
import asyncio
from datetime import datetime, timezone

from scraper_agent.parser.article_extractor import extract_article
from scraper_agent.parser.html_parser import is_cloudflare_challenge
from scraper_agent.renderer.playwright_renderer import PlaywrightRenderer

URLS = [
    "https://www.expreso.com.pe/actualidad/temblor-hoy-5-de-julio-de-2026-en-ica-epicentro-magnitud-y-reporte-oficial-del-igp-hace-minutos-instituto-geofisico-del-peru-terremoto-sismo-indeci-emergencia-noticia/1299300",
    "https://www.expreso.com.pe/judicial/caso-gasoducto-sur-pj-archiva-acusacion-por-asociacion-ilicita-contra-ollanta-humala-nadine-heredia-y-otros-estado-noticia/1299285",
]


async def main() -> None:
    r = PlaywrightRenderer()
    await r.start()
    for url in URLS:
        html = await r.render(url, wait_until="load")
        ok = not is_cloudflare_challenge(html)
        art = extract_article(url, html, 200, datetime.now(timezone.utc), site_name="expreso.com.pe")
        pub = (art or {}).get("dates", {}).get("published_at")
        print(ok, len(html), pub)
        await asyncio.sleep(3)
    await r.stop()


if __name__ == "__main__":
    asyncio.run(main())
