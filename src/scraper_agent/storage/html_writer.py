"""Genera HTML legible a partir de salida scraper-schema.json."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _render_runs(block: dict[str, Any]) -> str:
    runs = block.get("runs") or []
    if not runs:
        return _esc(block.get("text", ""))
    parts: list[str] = []
    for run in runs:
        text = _esc(run.get("text", ""))
        if run.get("kind") == "link" and run.get("url"):
            parts.append(f'<a href="{_esc(run["url"])}" target="_blank" rel="noopener">{text}</a>')
        else:
            parts.append(text)
    return "".join(parts)


def _render_block(block: dict[str, Any]) -> str:
    btype = block.get("type", "paragraph")
    order = block.get("order", 0)
    if btype == "heading":
        level = min(max(int(block.get("level") or 2), 1), 6)
        return f'<h{level} class="block" data-order="{order}">{_esc(block.get("text"))}</h{level}>'
    if btype == "quote":
        return (
            f'<blockquote class="block quote" data-order="{order}">'
            f'{_esc(block.get("text"))}</blockquote>'
        )
    if btype == "related_link":
        label = block.get("label")
        prefix = f'<strong>{_esc(label)}:</strong> ' if label else ""
        return (
            f'<p class="block related-link" data-order="{order}">{prefix}'
            f'<a href="{_esc(block.get("url"))}" target="_blank" rel="noopener">'
            f'{_esc(block.get("text"))}</a></p>'
        )
    if btype == "image_caption":
        return f'<p class="block caption" data-order="{order}"><em>{_esc(block.get("text"))}</em></p>'
    if btype == "list_item":
        return f'<li class="block" data-order="{order}">{_render_runs(block)}</li>'
    return f'<p class="block" data-order="{order}">{_render_runs(block)}</p>'


def _render_article(article: dict[str, Any], index: int) -> str:
    headline = article.get("headline") or {}
    dates = article.get("dates") or {}
    media = article.get("media") or {}
    cover = (media.get("cover_image") or {}).get("url")
    blocks = article.get("content_blocks") or []
    authorship = article.get("authorship") or {}
    authors = ", ".join(a.get("name", "") for a in authorship.get("authors") or [] if a.get("name"))

    block_html: list[str] = []
    in_list = False
    for block in sorted(blocks, key=lambda b: b.get("order", 0)):
        if block.get("type") == "list_item":
            if not in_list:
                block_html.append("<ul>")
                in_list = True
            block_html.append(_render_block(block))
        else:
            if in_list:
                block_html.append("</ul>")
                in_list = False
            block_html.append(_render_block(block))
    if in_list:
        block_html.append("</ul>")

    cover_html = ""
    if cover:
        cover_html = (
            f'<figure class="cover"><img src="{_esc(cover)}" alt="" loading="lazy">'
            f"</figure>"
        )

    subtitle = headline.get("subtitle")
    subtitle_html = f'<p class="subtitle">{_esc(subtitle)}</p>' if subtitle else ""

    return f"""
<article class="article" id="article-{index}">
  <header>
    <h1>{_esc(headline.get("title"))}</h1>
    {subtitle_html}
    <p class="meta">
      <span>{_esc(dates.get("published_at"))}</span>
      {f" · <span>{_esc(authors)}</span>" if authors else ""}
      · <a href="{_esc(article.get("url"))}" target="_blank" rel="noopener">URL original</a>
    </p>
  </header>
  {cover_html}
  <div class="body">
    {"".join(block_html)}
  </div>
</article>
"""


def _highlight_markers(text: str) -> str:
    """Convierte [[término]] en <mark> para HTML."""
    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        start = text.find("[[", cursor)
        if start < 0:
            parts.append(_esc(text[cursor:]))
            break
        parts.append(_esc(text[cursor:start]))
        end = text.find("]]", start + 2)
        if end < 0:
            parts.append(_esc(text[start:]))
            break
        inner = text[start + 2 : end]
        parts.append(f"<mark>{_esc(inner)}</mark>")
        cursor = end + 2
    return "".join(parts)


def _render_search_summary(
    payload: dict[str, Any],
    articles_by_id: dict[str, dict[str, Any]],
) -> str:
    results = payload.get("search_results") or []
    if not results:
        return ""

    rows: list[str] = []
    for result in results:
        article = articles_by_id.get(result.get("article_id", ""), {})
        headline = (article.get("headline") or {}).get("title", "")
        dates = (article.get("dates") or {}).get("published_at", "")
        domain = result.get("domain") or (payload.get("crawl_metadata") or {}).get("domain", "")
        terms = ", ".join(result.get("matched_terms") or [])
        rows.append(
            "<tr>"
            f"<td>{result.get('score', 0):.2f}</td>"
            f"<td>{_esc(headline)}</td>"
            f"<td>{_esc(dates)}</td>"
            f"<td>{_esc(domain)}</td>"
            f"<td>{_esc(terms)}</td>"
            "</tr>"
        )

    matched_ids = {result.get("article_id") for result in results}
    detail_blocks: list[str] = []
    for result in results:
        article = articles_by_id.get(result.get("article_id", ""))
        if not article:
            continue
        snippets = result.get("matched_snippets") or []
        snippet_html = "".join(
            f'<p class="snippet"><strong>{_esc(snippet.get("field"))}:</strong> '
            f"{_highlight_markers(str(snippet.get('text', '')))}</p>"
            for snippet in snippets
        )
        title = (article.get("headline") or {}).get("title", "")
        detail_blocks.append(
            f'<section class="search-hit"><h3>{_esc(title)}</h3>{snippet_html}</section>'
        )

    articles_html = "".join(
        _render_article(art, idx)
        for idx, art in enumerate(
            [articles_by_id[aid] for aid in matched_ids if aid in articles_by_id],
            start=1,
        )
    )

    return f"""
  <section class="search-results">
    <h2>Resultados de búsqueda</h2>
    <table>
      <thead>
        <tr><th>Score</th><th>Titular</th><th>Fecha</th><th>Sitio</th><th>Términos</th></tr>
      </thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    <div class="search-hits">{"".join(detail_blocks)}</div>
    <div class="matched-articles">{articles_html}</div>
  </section>
"""


def build_html_document(payload: dict[str, Any]) -> str:
    meta = payload.get("crawl_metadata") or {}
    quality = payload.get("extraction_quality") or {}
    articles = payload.get("articles") or []
    articles_by_id = {
        str(article.get("article_id")): article
        for article in articles
        if article.get("article_id")
    }
    search_html = _render_search_summary(payload, articles_by_id)
    if search_html:
        articles_html = ""
    else:
        articles_html = "".join(_render_article(art, i) for i, art in enumerate(articles, start=1))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Scraper — {_esc(meta.get("domain"))}</title>
  <style>
    :root {{ font-family: Georgia, "Times New Roman", serif; line-height: 1.6; color: #1a1a1a; }}
    body {{ max-width: 720px; margin: 0 auto; padding: 1.5rem; background: #fafafa; }}
    .crawl-meta {{ background: #fff; border: 1px solid #ddd; padding: 1rem; margin-bottom: 2rem; font-size: 0.9rem; }}
    .article {{ background: #fff; border: 1px solid #ddd; padding: 1.5rem; margin-bottom: 2rem; }}
    .article h1 {{ font-size: 1.6rem; line-height: 1.25; margin: 0 0 0.5rem; }}
    .subtitle {{ color: #555; font-size: 1.05rem; margin: 0 0 0.75rem; }}
    .meta {{ color: #777; font-size: 0.85rem; margin: 0 0 1rem; }}
    .cover img {{ max-width: 100%; height: auto; }}
    .block {{ margin: 0.75rem 0; }}
    .quote {{ border-left: 3px solid #c00; padding-left: 1rem; color: #333; }}
    .related-link a {{ color: #06c; font-weight: 600; }}
    .caption {{ color: #666; font-size: 0.95rem; }}
    a {{ color: #06c; }}
    .search-results table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; margin: 1rem 0; }}
    .search-results th, .search-results td {{ border: 1px solid #ddd; padding: 0.4rem 0.5rem; text-align: left; }}
    mark {{ background: #fff3a0; padding: 0 0.15rem; }}
    .search-hit {{ margin: 1.5rem 0; padding: 1rem; background: #fffef5; border: 1px solid #eed; }}
  </style>
</head>
<body>
  <section class="crawl-meta">
    <strong>Crawl:</strong> {_esc(meta.get("crawl_id"))}<br>
    <strong>Dominio:</strong> {_esc(meta.get("domain"))}<br>
    <strong>Artículos:</strong> {meta.get("total_articles_extracted", len(articles))}<br>
    <strong>Calidad:</strong> score {quality.get("confidence_score", "—")}
  </section>
  {search_html}
  {articles_html}
</body>
</html>
"""


def write_html_report(json_path: str | Path, html_path: str | Path | None = None) -> Path:
    """Lee JSON del schema y escribe HTML legible."""
    src = Path(json_path)
    dest = Path(html_path) if html_path else src.with_suffix(".html")
    payload = json.loads(src.read_text(encoding="utf-8"))
    dest.write_text(build_html_document(payload), encoding="utf-8")
    return dest
