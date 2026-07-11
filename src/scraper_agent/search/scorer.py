"""Puntuación de relevancia para resultados de búsqueda."""

from __future__ import annotations

import math
from dataclasses import dataclass

from scraper_agent.models.search_target import SearchTarget
from scraper_agent.search.types import MatchResult, normalize_text

FIELD_WEIGHTS: dict[str, float] = {
    "headline": 3.0,
    "excerpt": 2.0,
    "content_blocks": 1.0,
    "outbound_links": 0.5,
    "authors": 1.0,
    "taxonomy": 1.5,
}


@dataclass(frozen=True)
class ScoredMatch:
    article_id: str
    raw_score: float
    normalized_score: float
    matches: tuple[MatchResult, ...]


def _has_exclude_hit(article_text: str, target: SearchTarget) -> bool:
    normalized = normalize_text(article_text)
    return any(normalize_text(term) in normalized for term in target.exclude_keywords)


def _keyword_requirement_met(matches: list[MatchResult], target: SearchTarget) -> bool:
    if not target.keywords and not target.patterns:
        return bool(matches)
    if not target.keywords:
        return bool(matches)
    matched_terms = {normalize_text(match.matched_term) for match in matches}
    required = {normalize_text(term) for term in target.keywords}
    if target.require_all:
        return required.issubset(matched_terms)
    return bool(matched_terms & required)


def score_article(
    article: dict,
    matches: list[MatchResult],
    target: SearchTarget,
    *,
    article_plain_text: str,
) -> float | None:
    """Calcula score bruto 0+; None si el artículo se descarta."""
    if target.exclude_keywords and _has_exclude_hit(article_plain_text, target):
        return None
    if not _keyword_requirement_met(matches, target):
        return None
    if not matches:
        return None

    score = 0.0
    seen: dict[tuple[str, str], int] = {}
    for match in matches:
        weight = FIELD_WEIGHTS.get(match.field, 1.0)
        key = (match.field, normalize_text(match.matched_term))
        count = seen.get(key, 0)
        seen[key] = count + 1
        score += weight * (1.0 / (1.0 + math.log1p(count)))
    return score


def normalize_scores(scored: list[ScoredMatch]) -> list[ScoredMatch]:
    """Normaliza scores al rango 0.0–1.0 relativo al máximo de la corrida."""
    if not scored:
        return []
    max_score = max(item.raw_score for item in scored)
    if max_score <= 0:
        return [
            ScoredMatch(
                article_id=item.article_id,
                raw_score=item.raw_score,
                normalized_score=0.0,
                matches=item.matches,
            )
            for item in scored
        ]
    return [
        ScoredMatch(
            article_id=item.article_id,
            raw_score=item.raw_score,
            normalized_score=round(item.raw_score / max_score, 4),
            matches=item.matches,
        )
        for item in scored
    ]


def build_search_result(scored: ScoredMatch) -> dict:
    """Convierte ScoredMatch al dict `search_results[]` del schema."""
    matched_fields = sorted({match.field for match in scored.matches})
    matched_terms = sorted({match.matched_term for match in scored.matches})
    snippets: list[dict[str, str]] = []
    seen_snippets: set[tuple[str, str]] = set()
    for match in scored.matches:
        key = (match.field, match.snippet)
        if key in seen_snippets:
            continue
        seen_snippets.add(key)
        snippets.append({"field": match.field, "text": match.snippet})
    return {
        "article_id": scored.article_id,
        "score": scored.normalized_score,
        "matched_fields": matched_fields,
        "matched_terms": matched_terms,
        "matched_snippets": snippets,
    }
