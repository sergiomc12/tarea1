"""Motor de búsqueda por objetivo profesional."""

from __future__ import annotations

from typing import Any

from scraper_agent.models.search_target import SearchTarget
from scraper_agent.search.matchers import article_plain_text, match_article
from scraper_agent.search.scorer import (
    ScoredMatch,
    build_search_result,
    normalize_scores,
    score_article,
)


def search_articles(
    articles: list[dict[str, Any]],
    target: SearchTarget,
) -> list[dict[str, Any]]:
    """Filtra, puntúa y ordena artículos según el objetivo."""
    scored: list[ScoredMatch] = []
    for article in articles:
        matches = match_article(article, target)
        raw = score_article(
            article,
            matches,
            target,
            article_plain_text=article_plain_text(article),
        )
        if raw is None:
            continue
        article_id = article.get("article_id")
        if not article_id:
            continue
        scored.append(
            ScoredMatch(
                article_id=str(article_id),
                raw_score=raw,
                normalized_score=0.0,
                matches=tuple(matches),
            )
        )

    normalized = normalize_scores(scored)
    results = [
        build_search_result(item)
        for item in normalized
        if item.normalized_score >= target.min_score
    ]
    results.sort(key=lambda item: item["score"], reverse=True)
    return results


def apply_search_to_payload(payload: dict[str, Any], target: SearchTarget) -> dict[str, Any]:
    """Añade search_results y crawl_metadata.search_target al payload."""
    articles = payload.get("articles") or []
    search_results = search_articles(articles, target)
    crawl_metadata = dict(payload.get("crawl_metadata") or {})
    crawl_metadata["search_target"] = target.to_metadata()
    return {
        **payload,
        "crawl_metadata": crawl_metadata,
        "search_results": search_results,
    }
