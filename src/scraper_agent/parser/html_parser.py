"""Parseo HTML con BeautifulSoup."""

import re

from bs4 import BeautifulSoup


def parse_html(html: str) -> BeautifulSoup:
    """Parsea HTML con lxml."""
    return BeautifulSoup(html, "lxml")


def extract_title(soup: BeautifulSoup) -> str:
    """Extrae el título de la página."""
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def needs_js_render(html: str) -> bool:
    """Heurística: ¿requiere render JS?"""
    lower = html.lower()
    if is_cloudflare_challenge(html):
        return True
    if 'id="root"' in lower or 'id="app"' in lower:
        body = parse_html(html).find("body")
        if body and len(body.get_text(strip=True)) < 200:
            return True
    if "react" in lower or "vue" in lower or "__next" in lower:
        soup = parse_html(html)
        body = soup.find("body")
        if body and len(body.get_text(strip=True)) < 300:
            return True
    return False


def is_cloudflare_challenge(html: str) -> bool:
    """True si la respuesta parece un challenge o bloqueo de Cloudflare."""
    lower = (html or "")[:4000].lower()
    if "cdn-cgi/challenge-platform" in lower:
        return True
    if "cf-browser-verification" in lower:
        return True
    if "attention required" in lower and "cloudflare" in lower:
        return True
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", lower, re.I)
    if title_match:
        title = title_match.group(1).lower()
        if "just a moment" in title or "un momento" in title:
            return True
    return False
