"""Matchers de coincidencia sobre artículos."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from scraper_agent.models.search_target import SearchTarget
from scraper_agent.parser.article_extractor import article_in_date_range
from scraper_agent.search.types import MatchResult, normalize_text


def _parse_target_date(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if len(raw) == 10:
        raw = f"{raw}T00:00:00Z"
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def _mark_snippet(text: str, term: str) -> str:
    """Envuelve la primera coincidencia con [[…]]."""
    normalized_text = normalize_text(text)
    normalized_term = normalize_text(term)
    idx = normalized_text.find(normalized_term)
    if idx < 0:
        return text
    end = idx + len(term)
    return f"{text[:idx]}[[{text[idx:end]}]]{text[end:]}"


def _dedupe_matches(matches: list[MatchResult]) -> list[MatchResult]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[MatchResult] = []
    for match in matches:
        key = (match.field, match.matched_term, match.snippet)
        if key in seen:
            continue
        seen.add(key)
        unique.append(match)
    return unique


def collect_field_texts(article: dict[str, Any], fields: list[str]) -> dict[str, list[str]]:
    collected: dict[str, list[str]] = {field: [] for field in fields}
    headline = article.get("headline") or {}
    summary = article.get("summary") or {}
    authorship = article.get("authorship") or {}
    links = article.get("links") or {}

    if "headline" in collected:
        for key in ("title", "subtitle", "kicker"):
            value = headline.get(key)
            if value:
                collected["headline"].append(str(value))

    if "excerpt" in collected:
        for key in ("excerpt", "meta_description", "og_description"):
            value = summary.get(key)
            if value:
                collected["excerpt"].append(str(value))

    if "authors" in collected:
        for author in authorship.get("authors") or []:
            name = author.get("name")
            if name:
                collected["authors"].append(str(name))

    if "taxonomy" in collected:
        taxonomy = article.get("taxonomy") or {}
        for key in ("primary_category",):
            value = taxonomy.get(key)
            if value:
                collected["taxonomy"].append(str(value))
        for key in ("secondary_categories", "tags", "related_topics"):
            for value in taxonomy.get(key) or []:
                if value:
                    collected["taxonomy"].append(str(value))

    if "content_blocks" in collected:
        for block in article.get("content_blocks") or []:
            text = block.get("text")
            if text:
                collected["content_blocks"].append(str(text))

    if "outbound_links" in collected:
        for link in links.get("outbound_links") or []:
            anchor = link.get("anchor_text") or link.get("text") or ""
            url = link.get("url") or ""
            combined = f"{anchor} {url}".strip()
            if combined:
                collected["outbound_links"].append(combined)

    return collected


def article_plain_text(article: dict[str, Any]) -> str:
    parts: list[str] = []
    for values in collect_field_texts(
        article,
        ["headline", "excerpt", "content_blocks", "outbound_links", "authors", "taxonomy"],
    ).values():
        parts.extend(values)
    return " ".join(parts)


def _text_matches(field: str, texts: list[str], target: SearchTarget) -> list[MatchResult]:
    results: list[MatchResult] = []
    for text in texts:
        normalized = normalize_text(text)
        for keyword in target.keywords:
            term = normalize_text(keyword)
            if term and term in normalized:
                results.append(
                    MatchResult(
                        field=field,
                        matched_term=keyword,
                        snippet=_mark_snippet(text, keyword),
                    )
                )
    return results


def _pattern_matches(field: str, texts: list[str], target: SearchTarget) -> list[MatchResult]:
    results: list[MatchResult] = []
    for text in texts:
        for pattern in target.patterns:
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                continue
            match = regex.search(text)
            if not match:
                continue
            fragment = match.group(1) if match.lastindex else match.group(0)
            results.append(
                MatchResult(
                    field=field,
                    matched_term=fragment,
                    snippet=_mark_snippet(text, fragment),
                )
            )
    return results


def _date_match(article: dict[str, Any], target: SearchTarget) -> list[MatchResult]:
    if not target.date_range:
        return []
    date_from = _parse_target_date(target.date_range.from_date)
    date_to = _parse_target_date(target.date_range.to_date)
    if article_in_date_range(article, date_from, date_to):
        pub = (article.get("dates") or {}).get("published_at") or ""
        return [
            MatchResult(
                field="dates",
                matched_term=str(pub),
                snippet=str(pub),
            )
        ]
    return []


def match_article(article: dict[str, Any], target: SearchTarget) -> list[MatchResult]:
    """Ejecuta matchers sobre un artículo."""
    if target.date_range:
        date_from = _parse_target_date(target.date_range.from_date)
        date_to = _parse_target_date(target.date_range.to_date)
        if not article_in_date_range(article, date_from, date_to):
            return []

    field_texts = collect_field_texts(article, target.match_in)
    matches: list[MatchResult] = []
    for field, texts in field_texts.items():
        matches.extend(_text_matches(field, texts, target))
        matches.extend(_pattern_matches(field, texts, target))
    matches.extend(_date_match(article, target))
    return _dedupe_matches(matches)
