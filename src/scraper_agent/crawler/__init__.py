"""Crawler recursivo."""

from scraper_agent.crawler.orchestrator import CrawlOrchestrator
from scraper_agent.crawler.scope import CrawlScope
from scraper_agent.crawler.url_frontier import UrlFrontier

__all__ = ["CrawlOrchestrator", "CrawlScope", "UrlFrontier"]
