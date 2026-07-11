"""Inspect expreso HTML structure."""
import asyncio
import re

from scraper_agent.renderer.playwright_renderer import PlaywrightRenderer


async def main() -> None:
    r = PlaywrightRenderer()
    await r.start()
    page = await r._context.new_page()
    await page.goto("https://www.expreso.com.pe/", wait_until="networkidle", timeout=120000)
    html = await page.content()
    await page.close()

    # URL patterns in raw HTML
    patterns = [
        r"https://www\.expreso\.com\.pe/[a-z0-9-]+/\d{4}/\d{2}/\d{2}/[a-z0-9-]+",
        r"https://www\.expreso\.com\.pe/[a-z0-9-]+/[a-z0-9-]+",
        r'href="(/[^"]+)"',
    ]
    for pat in patterns[:2]:
        found = sorted(set(re.findall(pat, html, re.I)))
        print(pat, "count", len(found), found[:5])

    # JSON-LD or embedded data
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S | re.I):
        snippet = m.group(1)[:200]
        print("ld+json:", snippet)

    # article tags
    print("article tags", len(re.findall(r"<article", html, re.I)))

    # sitemap
    page2 = await r._context.new_page()
    await page2.goto("https://www.expreso.com.pe/sitemap.xml", wait_until="networkidle", timeout=120000)
    sm = await page2.content()
    await page2.close()
    print("sitemap <loc>", sm.lower().count("<loc"))
    locs = re.findall(r"<loc>([^<]+)</loc>", sm)
    print("locs regex", len(locs), locs[:5])
    print("sitemap snippet", sm[sm.find("<loc") : sm.find("<loc") + 500] if "<loc" in sm else sm[:500])

    await r.stop()


if __name__ == "__main__":
    asyncio.run(main())
