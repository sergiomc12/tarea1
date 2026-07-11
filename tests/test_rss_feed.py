"""Tests de parseo RSS/Atom."""

from scraper_agent.parser.rss_feed import parse_rss_feed

RSS_SAMPLE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Nota A</title><link>https://gestion.pe/economia/nota-a/</link></item>
<item><title>Nota B</title><link>https://gestion.pe/economia/nota-b/</link></item>
</channel></rss>"""

ATOM_SAMPLE = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom</title><link href="https://ojo.pe/nota-atom/"/></entry>
</feed>"""


def test_parse_rss_items():
    items = parse_rss_feed(RSS_SAMPLE)
    assert len(items) == 2
    assert items[0]["url"] == "https://gestion.pe/economia/nota-a/"
    assert items[0]["title"] == "Nota A"


def test_parse_atom_entries():
    items = parse_rss_feed(ATOM_SAMPLE)
    assert len(items) == 1
    assert items[0]["url"] == "https://ojo.pe/nota-atom/"


def test_parse_invalid_xml():
    assert parse_rss_feed("not xml") == []


def test_parse_rss_wrapped_in_html_pre():
    wrapped = """<html><body><pre>&lt;?xml version="1.0"?&gt;
&lt;rss version="2.0"&gt;&lt;channel&gt;
&lt;item&gt;&lt;title&gt;Nota&lt;/title&gt;&lt;link&gt;https://peru21.pe/nota/&lt;/link&gt;&lt;/item&gt;
&lt;/channel&gt;&lt;/rss&gt;</pre></body></html>"""
    items = parse_rss_feed(wrapped)
    assert len(items) == 1
    assert items[0]["url"] == "https://peru21.pe/nota/"
