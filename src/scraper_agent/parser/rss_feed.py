"""Parseo de feeds RSS 2.0 y Atom para descubrimiento de URLs de noticias."""

from __future__ import annotations

import html
import re
from xml.etree import ElementTree as ET

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def normalize_feed_xml(raw: str) -> str:
    """Convierte respuestas HTML-wrapped (Playwright) a XML parseable."""
    text = raw.strip()
    if text.startswith("<?xml") or text.startswith("<rss") or text.startswith("<feed"):
        return text
    pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", text, re.DOTALL | re.IGNORECASE)
    if pre_match:
        return html.unescape(pre_match.group(1)).strip()
    return text


def parse_rss_feed(xml_text: str) -> list[dict[str, str]]:
    """Devuelve [{'url': ..., 'title': ...}] desde un feed RSS o Atom."""
    xml_text = normalize_feed_xml(xml_text)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        link = (item.findtext("link") or "").strip()
        title = (item.findtext("title") or "").strip()
        if link:
            items.append({"url": link, "title": title})

    if items:
        return items

    for entry in root.findall(f".//{ATOM_NS}entry"):
        link_el = entry.find(f"{ATOM_NS}link")
        link = ""
        if link_el is not None:
            link = (link_el.get("href") or "").strip()
        title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
        if link:
            items.append({"url": link, "title": title})

    return items
