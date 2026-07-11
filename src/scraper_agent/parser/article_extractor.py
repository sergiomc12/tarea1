"""Extracción de artículos periodísticos al formato scraper-schema.json."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from scraper_agent.cleaning.normalizer import clean_text
from scraper_agent.parser.html_parser import extract_title, parse_html
from scraper_agent.utils.url_utils import normalize_url, resolve_url

PAYWALL_PATTERNS = (
    "exclusivo para suscriptores",
    "contenido exclusivo",
    "suscríbete",
    "suscribete",
    "plus g",
    "premium",
)


def generate_article_id(url: str, published_at: str | None) -> str:
    """Hash determinístico dominio + slug + fecha."""
    parsed = urlparse(url)
    slug = parsed.path.strip("/").replace("/", "-") or "home"
    base = f"{parsed.netloc}|{slug}|{published_at or 'unknown'}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
    return f"{parsed.netloc.split('.')[0]}-{digest}"


def _parse_datetime(raw: str | None) -> tuple[str | None, str | None]:
    if not raw or not str(raw).strip():
        return None, raw
    text = str(raw).strip()
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", text):
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), text
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), text
    except (ValueError, TypeError, OverflowError):
        return None, text


def _meta_content(soup: BeautifulSoup, *selectors: str) -> str | None:
    for sel in selectors:
        if sel.startswith("link[rel="):
            tag = soup.find("link", rel="canonical")
            if tag and tag.get("href"):
                return clean_text(tag["href"])
            continue
        tag = soup.select_one(sel)
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return None


EXCLUDED_CONTAINER_HINTS = (
    "most-read",
    "related",
    "recommend",
    "widget",
    "link-list",
    "related-content",
    "copy-blocker",
    "story-contents__social",
)

BOILERPLATE_ELEMENT_HINTS = (
    "about-author",
    "author-bio",
    "copy-blocker",
)

READ_ALSO_RE = re.compile(r"^LEA TAMBI[ÉE]N", re.IGNORECASE)
CAPTION_RE = re.compile(r"\(Foto:|Foto:", re.IGNORECASE)
MIN_ARTICLE_BODY_CHARS = 300
BODY_BLOCK_TYPES = frozenset({"paragraph", "quote", "list_item"})

ARTICLE_ROOT_SELECTORS = (
    ".story-contents",
    ".st-sidebar__container .story-contents",
    "article.story-body",
    "[class*='story-contents']",
    "[class*='story-body']",
    "article[itemprop='articleBody']",
    "main article",
)


def _container_class_hint(node: Tag) -> str:
    return " ".join(node.get("class") or []).lower()


def _is_excluded_container(node: Tag) -> bool:
    hint = _container_class_hint(node)
    return any(token in hint for token in EXCLUDED_CONTAINER_HINTS)


def _score_article_root(node: Tag) -> int:
    if _is_excluded_container(node):
        return -1
    paragraphs = len(node.find_all("p", recursive=True))
    if paragraphs == 0:
        return -1
    headings = len(node.find_all(["h1", "h2"], recursive=True))
    return paragraphs * 10 + headings


def _find_article_root(soup: BeautifulSoup) -> Tag | BeautifulSoup:
    candidates: list[Tag] = []
    seen: set[int] = set()

    def add_candidate(node: Tag | None) -> None:
        if node is None or id(node) in seen:
            return
        seen.add(id(node))
        candidates.append(node)

    for sel in ARTICLE_ROOT_SELECTORS:
        for node in soup.select(sel):
            if isinstance(node, Tag):
                add_candidate(node)

    for node in soup.find_all("article"):
        if isinstance(node, Tag):
            add_candidate(node)

    main = soup.select_one("main")
    if isinstance(main, Tag):
        add_candidate(main)

    best: Tag | None = None
    best_score = -1
    for node in candidates:
        score = _score_article_root(node)
        if score > best_score:
            best_score = score
            best = node

    if best is not None:
        return best
    return soup


def _in_excluded_region(el: Tag, root: Tag | BeautifulSoup) -> bool:
    """Excluye nodos fuera del contenedor elegido o dentro de widgets embebidos."""
    for parent in el.parents:
        if parent is root:
            return False
        if not isinstance(parent, Tag):
            continue
        if parent.name in {"aside", "nav", "footer", "header"}:
            return True
        hint = _container_class_hint(parent)
        if any(token in hint for token in EXCLUDED_CONTAINER_HINTS):
            return True
    return False


def _is_boilerplate_element(el: Tag) -> bool:
    hint = _container_class_hint(el)
    if any(token in hint for token in BOILERPLATE_ELEMENT_HINTS):
        return True
    for parent in el.parents:
        if not isinstance(parent, Tag):
            continue
        if any(token in _container_class_hint(parent) for token in BOILERPLATE_ELEMENT_HINTS):
            return True
    return False


def _parse_read_also_block(el: Tag, base_url: str) -> dict[str, Any] | None:
    text = clean_text(el.get_text(" ", strip=True))
    if not READ_ALSO_RE.search(text):
        return None
    anchor = el.find("a", href=True)
    if not anchor:
        return None
    link_text = clean_text(anchor.get_text())
    if not link_text:
        return None
    return {
        "type": "related_link",
        "text": link_text,
        "url": resolve_url(base_url, anchor["href"]),
        "label": "LEA TAMBIÉN",
    }


def _extract_header_related_links(soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
    """Enlaces bajo el titular (ej. ul.sht__list en gestion.pe)."""
    blocks: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for anchor in soup.select(".sht__list a[href]"):
        link_text = clean_text(anchor.get_text())
        href = resolve_url(base_url, anchor.get("href", ""))
        if not link_text or not href or href in seen_urls:
            continue
        seen_urls.add(href)
        blocks.append(
            {
                "type": "related_link",
                "text": link_text,
                "url": href,
                "label": None,
            }
        )
    return blocks


def _extract_image_caption_blocks(article_root: Tag | BeautifulSoup) -> list[dict[str, Any]]:
    """Captions en divs sueltos (gestion.pe: texto con 'Foto:')."""
    blocks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for div in article_root.find_all("div"):
        if div.find(["p", "h1", "h2", "h3", "h4", "blockquote", "ul", "ol"]):
            continue
        if _is_boilerplate_element(div):
            continue
        text = clean_text(div.get_text(" ", strip=True))
        if not text or len(text) < 20 or text in seen:
            continue
        if not CAPTION_RE.search(text):
            continue
        seen.add(text)
        blocks.append({"type": "image_caption", "text": text})
    return blocks


def _append_deck_paragraph(
    blocks: list[dict[str, Any]],
    *,
    order: int,
    subtitle: str | None,
) -> int:
    if not subtitle:
        return order
    deck = clean_text(subtitle)
    if not deck:
        return order
    if blocks and deck in blocks[0].get("text", ""):
        return order
    blocks.append({"type": "paragraph", "order": order, "text": deck})
    return order + 1


def _detect_paywall(soup: BeautifulSoup, html: str) -> dict[str, Any]:
    text = html.lower()
    is_paywalled = any(p in text for p in PAYWALL_PATTERNS)
    paywall_type = None
    if is_paywalled:
        if "suscriptor" in text or "plus" in text:
            paywall_type = "subscriber_only"
        else:
            paywall_type = "metered"
    return {
        "is_paywalled": is_paywalled,
        "paywall_type": paywall_type,
        "requires_login": False,
    }


def _author_record(
    name: str,
    base_url: str,
    *,
    author_url: str | None = None,
    byline_raw: str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    href = resolve_url(base_url, author_url) if author_url else None
    return {
        "name": name,
        "author_url": href,
        "role": role,
        "byline_raw": byline_raw,
    }


_BYLINE_PREFIX_RE = re.compile(r"^(por|by)\s+", re.IGNORECASE)
_SKIP_BREADCRUMB_LABELS = frozenset({"inicio", "home", "portada", ""})
_GENERIC_AUTHOR_LABELS = frozenset(
    {
        "redacción",
        "redaccion",
        "staff",
        "equipo editorial",
        "redacción gestión",
        "redacción gestion",
        "redacción ojo",
        "redacción el comercio",
    }
)


def _coerce_json_ld_authors(author_field: Any, base_url: str) -> list[dict[str, Any]]:
    if not author_field:
        return []
    items = author_field if isinstance(author_field, list) else [author_field]
    authors: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            name = clean_text(item)
            if name and name.lower() not in _GENERIC_AUTHOR_LABELS:
                authors.append(_author_record(name, base_url))
            continue
        if not isinstance(item, dict):
            continue
        name = clean_text(str(item.get("name") or ""))
        if not name or name.lower() in _GENERIC_AUTHOR_LABELS:
            continue
        url = item.get("url") or item.get("@id")
        authors.append(
            _author_record(
                name,
                base_url,
                author_url=str(url) if url else None,
            )
        )
    return authors


def _parse_byline_text(text: str) -> tuple[str | None, str | None]:
    """Devuelve (nombre, byline_raw) si el texto parece una firma."""
    cleaned = clean_text(text)
    if not cleaned:
        return None, None
    lowered = cleaned.lower()
    if lowered in _GENERIC_AUTHOR_LABELS:
        return None, None
    match = _BYLINE_PREFIX_RE.match(cleaned)
    if match:
        name = clean_text(cleaned[match.end() :])
        return (name, cleaned) if name else (None, None)
    if 1 <= len(cleaned.split()) <= 6 and ":" not in cleaned:
        return cleaned, cleaned
    return None, None


def _split_keywords(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [clean_text(str(item)) for item in raw if clean_text(str(item))]
    if isinstance(raw, str):
        return [clean_text(part) for part in re.split(r"[,;|]", raw) if clean_text(part)]
    return []


def _topics_from_json_ld(about_field: Any) -> list[str]:
    if not about_field:
        return []
    items = about_field if isinstance(about_field, list) else [about_field]
    topics: list[str] = []
    for item in items:
        if isinstance(item, str):
            label = clean_text(item)
        elif isinstance(item, dict):
            label = clean_text(str(item.get("name") or item.get("@id") or ""))
        else:
            label = ""
        if label:
            topics.append(label)
    return topics


def _extract_authors(
    soup: BeautifulSoup,
    base_url: str,
    ld: dict[str, Any] | None = None,
) -> dict[str, Any]:
    authors: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_author(
        name: str,
        *,
        author_url: str | None = None,
        byline_raw: str | None = None,
        role: str | None = None,
    ) -> None:
        normalized = clean_text(name).lower()
        if not normalized or normalized in seen or normalized in _GENERIC_AUTHOR_LABELS:
            return
        seen.add(normalized)
        authors.append(
            _author_record(name, base_url, author_url=author_url, byline_raw=byline_raw, role=role)
        )

    for person in _coerce_json_ld_authors((ld or {}).get("author"), base_url):
        add_author(person["name"], author_url=person.get("author_url"), byline_raw=person.get("byline_raw"))

    for sel in (
        "a[rel='author']",
        ".author-name a",
        ".story-body__author a",
        ".story-body-author__name",
        "a[href*='/autor/']",
        "[class*='author'] a[href]",
        ".sht__author a",
    ):
        for node in soup.select(sel):
            href = None
            if node.name == "a":
                name = clean_text(node.get_text())
                href = node.get("href")
            else:
                inner = node.find("a")
                if inner:
                    name = clean_text(inner.get_text())
                    href = inner.get("href")
                else:
                    name = clean_text(node.get_text())
            if name:
                add_author(name, author_url=resolve_url(base_url, href) if href else None)

    for sel in (".author-name", ".story-byline", "[class*='byline']", ".post-author", ".firma"):
        for node in soup.select(sel):
            if node.find("a"):
                continue
            name, byline_raw = _parse_byline_text(node.get_text(" ", strip=True))
            if name:
                add_author(name, byline_raw=byline_raw)

    agency = _meta_content(soup, "meta[name='author']", "meta[property='article:author']")
    return {"authors": authors, "editor": None, "agency_source": agency}


def _extract_taxonomy(
    soup: BeautifulSoup,
    url: str,
    ld: dict[str, Any] | None,
    identification: dict[str, Any],
) -> dict[str, Any]:
    ld = ld or {}
    section_raw = ld.get("articleSection") or _meta_content(soup, "meta[property='article:section']")
    if isinstance(section_raw, list):
        primary = clean_text(str(section_raw[0])) if section_raw else None
        extra_sections = [clean_text(str(item)) for item in section_raw[1:] if clean_text(str(item))]
    else:
        primary = clean_text(str(section_raw)) if section_raw else None
        extra_sections = []

    if not primary:
        primary = clean_text(identification.get("section") or "") or None

    breadcrumbs = [
        clean_text(label)
        for label in identification.get("breadcrumbs") or []
        if clean_text(label) and clean_text(label).lower() not in _SKIP_BREADCRUMB_LABELS
    ]
    secondary: list[str] = []
    for label in breadcrumbs + extra_sections:
        if label and label != primary and label not in secondary:
            secondary.append(label)

    tags: list[str] = []
    for meta in soup.select("meta[property='article:tag']"):
        value = clean_text(meta.get("content", ""))
        if value and value not in tags:
            tags.append(value)

    for key_source in (
        _meta_content(soup, "meta[name='keywords']", "meta[property='keywords']"),
        ld.get("keywords"),
    ):
        for keyword in _split_keywords(key_source):
            if keyword not in tags:
                tags.append(keyword)

    for sel in ("a[rel='tag']", ".tags a", "[class*='tag'] a", ".entry-tags a"):
        for anchor in soup.select(sel):
            label = clean_text(anchor.get_text())
            if label and label not in tags:
                tags.append(label)

    related_topics = _topics_from_json_ld(ld.get("about"))
    for topic in secondary:
        if topic not in related_topics:
            related_topics.append(topic)

    return {
        "primary_category": primary,
        "secondary_categories": secondary,
        "tags": tags,
        "related_topics": related_topics,
    }


def _extract_section(soup: BeautifulSoup, url: str) -> dict[str, Any]:
    section = _meta_content(soup, "meta[property='article:section']") or ""
    breadcrumbs = [clean_text(a.get_text()) for a in soup.select("nav.breadcrumb a, .breadcrumb a") if a.get_text(strip=True)]
    if not section and breadcrumbs:
        section = breadcrumbs[-1]
    if not section:
        path_parts = [p for p in urlparse(url).path.split("/") if p and p not in ("noticias", "news")]
        section = path_parts[0].replace("-", " ").title() if path_parts else "General"
    site_name = _meta_content(soup, "meta[property='og:site_name']") or urlparse(url).netloc
    is_premium = "plus" in url.lower() or bool(soup.select("[class*='premium']"))
    return {
        "site_name": site_name or urlparse(url).netloc,
        "section": section or "General",
        "subsection": breadcrumbs[-2] if len(breadcrumbs) > 1 else None,
        "breadcrumbs": breadcrumbs,
        "is_premium": is_premium,
        "premium_label": "PLUS G" if is_premium else None,
    }


def _append_text_run(runs: list[dict[str, Any]], fragment: str) -> None:
    if not fragment:
        return
    if runs and runs[-1]["kind"] == "text":
        runs[-1]["text"] += fragment
    else:
        runs.append({"kind": "text", "text": fragment})


def _build_text_runs(el: Tag, base_url: str, plain_text: str) -> list[dict[str, Any]] | None:
    """Genera runs[] cuando hay enlaces inline; concat(runs[].text) debe igualar plain_text."""
    if not el.find("a"):
        return None

    anchors = [a for a in el.find_all("a", href=True)]
    if len(anchors) == 1 and clean_text(anchors[0].get_text(" ", strip=True)) == plain_text:
        return None

    runs: list[dict[str, Any]] = []

    def walk(node: Tag | NavigableString) -> None:
        if isinstance(node, NavigableString):
            _append_text_run(runs, str(node))
            return
        if not isinstance(node, Tag):
            return
        if node.name in {"script", "style"}:
            return
        if node.name == "a":
            href = node.get("href")
            link_text = node.get_text("", strip=False)
            if href and link_text.strip():
                runs.append(
                    {
                        "kind": "link",
                        "text": clean_text(link_text),
                        "url": resolve_url(base_url, href),
                    }
                )
            elif link_text.strip():
                _append_text_run(runs, link_text)
            return
        if node.name == "br":
            _append_text_run(runs, " ")
            return
        for child in node.children:
            walk(child)

    for child in el.children:
        walk(child)

    if not any(r["kind"] == "link" for r in runs):
        return None

    joined = clean_text("".join(r["text"] for r in runs))
    if joined != plain_text:
        return None

    return runs


def build_content_blocks(
    article_root: Tag | BeautifulSoup,
    base_url: str = "",
    *,
    soup: BeautifulSoup | None = None,
    subtitle: str | None = None,
) -> list[dict[str, Any]]:
    """Mapea DOM a content_blocks ordenados."""
    blocks: list[dict[str, Any]] = []
    order = 0

    order = _append_deck_paragraph(blocks, order=order, subtitle=subtitle)

    if soup is not None:
        for link_block in _extract_header_related_links(soup, base_url):
            link_block["order"] = order
            blocks.append(link_block)
            order += 1

    for el in article_root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "li"], recursive=True):
        if _in_excluded_region(el, article_root) or _is_boilerplate_element(el):
            continue
        text = clean_text(el.get_text(" ", strip=True))
        if not text or len(text) < 2:
            continue
        if el.name == "blockquote":
            read_also = _parse_read_also_block(el, base_url)
            if read_also:
                read_also["order"] = order
                blocks.append(read_also)
                order += 1
                continue
            blocks.append({"type": "quote", "order": order, "text": text, "attribution": None})
        elif el.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(el.name[1])
            blocks.append({"type": "heading", "order": order, "text": text, "level": level})
        elif el.name == "li":
            block = {"type": "list_item", "order": order, "text": text, "list_id": None}
            runs = _build_text_runs(el, base_url, text)
            if runs:
                block["runs"] = runs
            blocks.append(block)
        else:
            block = {"type": "paragraph", "order": order, "text": text}
            runs = _build_text_runs(el, base_url, text)
            if runs:
                block["runs"] = runs
            blocks.append(block)
        order += 1

    for caption in _extract_image_caption_blocks(article_root):
        caption["order"] = order
        blocks.append(caption)
        order += 1

    return blocks


def _extract_media(
    article_root: Tag | BeautifulSoup,
    soup: BeautifulSoup,
    blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    cover_url = _meta_content(soup, "meta[property='og:image']", "meta[name='twitter:image']")
    cover_image = None
    if cover_url:
        cover_image = {"url": cover_url, "alt_text": None, "caption": None, "credit": None, "width": None, "height": None}

    inline: list[dict[str, Any]] = []
    last_order = blocks[-1]["order"] if blocks else 0
    for img in article_root.select("img"):
        src = img.get("src") or img.get("data-src")
        if not src or (cover_url and src in cover_url):
            continue
        inline.append(
            {
                "url": src,
                "alt_text": img.get("alt"),
                "caption": None,
                "credit": None,
                "width": None,
                "height": None,
                "position_after_block_order": last_order,
            }
        )
    return {"cover_image": cover_image, "inline_images": inline[:10], "videos": [], "embeds": []}


def _extract_outbound_links(
    article_root: Tag | BeautifulSoup,
    page_url: str,
    blocks: list[dict[str, Any]],
    site_domain: str,
) -> dict[str, Any]:
    outbound: list[dict[str, Any]] = []
    internal = 0
    external = 0
    last_order = blocks[-1]["order"] if blocks else 0
    for a in article_root.select("a[href]"):
        href = resolve_url(page_url, a.get("href", ""))
        anchor = clean_text(a.get_text())
        if not href or not anchor:
            continue
        host = urlparse(href).netloc.lower()
        if host == urlparse(page_url).netloc.lower():
            internal += 1
            link_type = "internal_reference"
        else:
            external += 1
            link_type = "external_source"
        if "lea tambien" in anchor.lower() or "relacionad" in anchor.lower():
            link_type = "related_article"
        outbound.append(
            {
                "url": href,
                "anchor_text": anchor,
                "type": link_type,
                "position_after_block_order": last_order,
            }
        )
    return {
        "outbound_links": outbound[:30],
        "internal_links_count": internal,
        "external_links_count": external,
    }


def _iter_json_ld_objects(soup: BeautifulSoup):
    """Recorre todos los dicts en bloques application/ld+json (incl. @graph)."""
    pending: list[Any] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        pending.extend(data if isinstance(data, list) else [data])

    while pending:
        item = pending.pop(0)
        if not isinstance(item, dict):
            continue
        graph = item.get("@graph")
        if isinstance(graph, list):
            pending.extend(x for x in graph if isinstance(x, dict))
            continue
        yield item


def _extract_json_ld_article(soup: BeautifulSoup) -> dict[str, Any]:
    for item in _iter_json_ld_objects(soup):
        t = item.get("@type", "")
        if t in ("NewsArticle", "Article", "BlogPosting") or "Article" in str(t):
            return item
    return {}


def _extract_json_ld_article_body(soup: BeautifulSoup) -> str:
    """Texto completo desde articleBody en JSON-LD (Arc / Grupo El Comercio)."""
    for item in _iter_json_ld_objects(soup):
        body = item.get("articleBody")
        if isinstance(body, str) and len(body.strip()) >= MIN_ARTICLE_BODY_CHARS:
            return body.strip()
    return ""


def _has_substantive_blocks(blocks: list[dict[str, Any]]) -> bool:
    return any(b.get("type") in BODY_BLOCK_TYPES for b in blocks)


def blocks_from_article_body(
    body: str,
    *,
    base_url: str,
    subtitle: str | None = None,
    soup: BeautifulSoup | None = None,
) -> list[dict[str, Any]]:
    """Convierte articleBody plano en content_blocks[] ordenados."""
    blocks: list[dict[str, Any]] = []
    order = 0
    order = _append_deck_paragraph(blocks, order=order, subtitle=subtitle)

    if soup is not None:
        for link_block in _extract_header_related_links(soup, base_url):
            link_block["order"] = order
            blocks.append(link_block)
            order += 1

    chunks = [clean_text(part) for part in re.split(r"\n\s*\n", body.strip()) if clean_text(part)]
    if len(chunks) <= 1:
        chunks = [clean_text(part) for part in body.split("\n") if len(clean_text(part)) >= 60]

    for chunk in chunks:
        if len(chunk) < 60:
            continue
        blocks.append({"type": "paragraph", "order": order, "text": chunk})
        order += 1

    return blocks


def extract_article(
    url: str,
    html: str,
    status_code: int,
    fetched_at: datetime,
    *,
    site_name: str | None = None,
) -> dict[str, Any] | None:
    """Extrae un artículo estructurado o None si la página no es un artículo."""
    soup = parse_html(html)
    article_root = _find_article_root(soup)
    ld = _extract_json_ld_article(soup)
    title = clean_text(ld.get("headline") or extract_title(soup) or _meta_content(soup, "meta[property='og:title']") or "")
    if not title:
        return None

    subtitle = _meta_content(soup, "meta[property='og:description']", "meta[name='description']")
    blocks = build_content_blocks(article_root, base_url=url, soup=soup, subtitle=subtitle)
    if not _has_substantive_blocks(blocks):
        body_text = _extract_json_ld_article_body(soup)
        if body_text:
            blocks = blocks_from_article_body(body_text, base_url=url, subtitle=subtitle, soup=soup)
    if not _has_substantive_blocks(blocks):
        return None

    pub_raw = ld.get("datePublished") or _meta_content(
        soup, "meta[property='article:published_time']", "meta[name='pubdate']", "time[datetime]"
    )
    if not pub_raw:
        time_tag = soup.select_one("time[datetime]")
        if time_tag:
            pub_raw = time_tag.get("datetime") or time_tag.get_text()
    published_at, published_at_raw = _parse_datetime(str(pub_raw) if pub_raw else None)

    updated_raw = ld.get("dateModified") or _meta_content(soup, "meta[property='article:modified_time']")
    updated_at, _ = _parse_datetime(str(updated_raw) if updated_raw else None)

    subtitle = _meta_content(soup, "meta[property='og:description']", "meta[name='description']")
    excerpt = clean_text(ld.get("description") or subtitle or "")

    article_id = generate_article_id(url, published_at)
    html_hash = f"sha256:{hashlib.sha256(html.encode('utf-8')).hexdigest()}"

    identification = _extract_section(soup, url)
    if site_name:
        identification["site_name"] = site_name

    article = {
        "article_id": article_id,
        "url": normalize_url(url),
        "canonical_url": _meta_content(soup, "link[rel='canonical']") or normalize_url(url),
        "amp_url": None,
        "fetch_info": {
            "status_code": status_code,
            "fetched_at": fetched_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "response_time_ms": None,
            "final_url_after_redirects": normalize_url(url),
            "html_hash": html_hash,
            "content_length_bytes": len(html.encode("utf-8")),
        },
        "identification": identification,
        "headline": {
            "title": title,
            "subtitle": subtitle,
            "kicker": None,
            "meta_title": _meta_content(soup, "meta[property='og:title']"),
            "og_title": _meta_content(soup, "meta[property='og:title']"),
        },
        "summary": {
            "excerpt": excerpt or None,
            "meta_description": _meta_content(soup, "meta[name='description']"),
            "og_description": _meta_content(soup, "meta[property='og:description']"),
        },
        "authorship": _extract_authors(soup, url, ld),
        "dates": {
            "published_at": published_at,
            "updated_at": updated_at,
            "published_at_raw": published_at_raw,
            "timezone": "America/Lima",
        },
        "taxonomy": _extract_taxonomy(soup, url, ld, identification),
        "content_blocks": blocks,
        "media": _extract_media(article_root, soup, blocks),
        "links": _extract_outbound_links(article_root, url, blocks, urlparse(url).netloc),
        "access": _detect_paywall(soup, html),
        "seo_and_metadata": {
            "canonical": _meta_content(soup, "link[rel='canonical']"),
            "robots_meta": _meta_content(soup, "meta[name='robots']"),
            "schema_org_type": ld.get("@type") if ld else None,
            "language": (soup.html.get("lang") if soup.html else None) or "es",
            "keywords_meta": [],
        },
        "raw_html_snapshot_ref": None,
    }
    return article


def classify_article_quality(article: dict[str, Any]) -> str:
    """Clasifica full | partial | failed."""
    blocks = article.get("content_blocks") or []
    title = (article.get("headline") or {}).get("title")
    published = (article.get("dates") or {}).get("published_at")
    if not title or len(blocks) < 1:
        return "failed"
    if len(blocks) >= 3 and published:
        return "full"
    return "partial"


def compute_extraction_quality(articles: list[dict[str, Any]]) -> dict[str, Any]:
    full = partial = failed = 0
    for art in articles:
        q = classify_article_quality(art)
        if q == "full":
            full += 1
        elif q == "partial":
            partial += 1
        else:
            failed += 1
    total = max(len(articles), 1)
    score = round(full / total, 2)
    return {
        "articles_fully_parsed": full,
        "articles_partial": partial,
        "articles_failed": failed,
        "confidence_score": score,
        "warnings": [],
    }


def article_in_date_range(
    article: dict[str, Any],
    date_from: datetime | None,
    date_to: datetime | None,
) -> bool:
    """Filtra por published_at; sin fecha se incluye solo si no hay filtro estricto."""
    if not date_from and not date_to:
        return True
    pub = (article.get("dates") or {}).get("published_at")
    if not pub:
        return date_from is None and date_to is None
    try:
        dt = datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
    except ValueError:
        return False
    if date_from and dt < date_from:
        return False
    if date_to and dt > date_to:
        return False
    return True
