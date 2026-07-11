"""Parser HTML y enlaces."""

from scraper_agent.parser.html_parser import extract_title, needs_js_render, parse_html
from scraper_agent.parser.link_extractor import extract_links, extract_sitemap_urls
from scraper_agent.parser.selectors import extract_with_selectors

__all__ = [
    "extract_links",
    "extract_sitemap_urls",
    "extract_title",
    "extract_with_selectors",
    "needs_js_render",
    "parse_html",
]
