"""Tests del crawler."""

from scraper_agent.crawler.scope import CrawlScope
from scraper_agent.crawler.url_frontier import UrlFrontier


def test_scope_allows_same_domain():
    scope = CrawlScope("https://example.com", include_subdomains=True, max_depth=3)
    assert scope.is_allowed("https://example.com/about") is True
    assert scope.is_allowed("https://sub.example.com/x") is True
    assert scope.is_allowed("https://other.com/x") is False


def test_scope_respects_max_depth():
    scope = CrawlScope("https://example.com", max_depth=1)
    assert scope.is_allowed("https://example.com/a") is True
    assert scope.is_allowed("https://example.com/a/b/c") is False


def test_scope_exclude_patterns():
    scope = CrawlScope("https://example.com", exclude_patterns=["/logout"])
    assert scope.is_allowed("https://example.com/logout") is False


def test_frontier_deduplication():
    frontier = UrlFrontier("https://example.com")
    assert frontier.enqueue("https://example.com/page") is True
    assert frontier.enqueue("https://example.com/page") is False
    frontier.mark_visited("https://example.com/page")
    assert frontier.was_visited("https://example.com/page") is True


def test_frontier_priority_queue():
    frontier = UrlFrontier("https://example.com", seed_queue=False)
    frontier.enqueue("https://example.com/low")
    frontier.enqueue_priority("https://example.com/high")
    assert frontier.dequeue() == "https://example.com/high"
