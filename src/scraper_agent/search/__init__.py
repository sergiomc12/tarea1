"""Búsqueda por objetivo profesional sobre artículos extraídos."""

from scraper_agent.search.query_engine import apply_search_to_payload, search_articles
from scraper_agent.search.types import MatchResult

__all__ = ["MatchResult", "apply_search_to_payload", "search_articles"]
