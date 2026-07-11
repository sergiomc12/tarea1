"""Tests del parser."""

from scraper_agent.parser.html_parser import extract_title, needs_js_render, parse_html
from scraper_agent.parser.link_extractor import extract_links, extract_sitemap_urls, is_sitemap_document
from scraper_agent.parser.selectors import extract_with_selectors

SAMPLE_HTML = """
<html><head><title>Demo</title></head>
<body>
  <a href="/page2">Page 2</a>
  <a href="https://external.com/x">Ext</a>
  <p class="price">S/ 10.00</p>
</body></html>
"""


def test_extract_title():
    soup = parse_html(SAMPLE_HTML)
    assert extract_title(soup) == "Demo"


def test_extract_links():
    links = extract_links(SAMPLE_HTML, "https://example.com/")
    assert "https://example.com/page2" in links
    assert "https://external.com/x" in links


def test_extract_with_selectors():
    soup = parse_html(SAMPLE_HTML)
    data = extract_with_selectors(soup, {"price": ".price"})
    assert data["price"] == "S/ 10.00"


def test_extract_sitemap_urls():
    xml = """<?xml version="1.0"?><urlset>
    <url><loc>https://example.com/a</loc></url></urlset>"""
    urls = extract_sitemap_urls(xml, "https://example.com")
    assert urls == ["https://example.com/a"]


def test_is_sitemap_document():
    xml = "<urlset><url><loc>https://example.com/a</loc></url></urlset>"
    assert is_sitemap_document("https://example.com/sitemap.xml", xml) is True
    assert is_sitemap_document("https://example.com/nota/", "<html><body>x</body></html>") is False


def test_needs_js_render_spa():
    html = '<html><body><div id="root"></div></body></html>'
    assert needs_js_render(html) is True
