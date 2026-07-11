"""Asegura que el formato legacy pages[].data no vuelva al código."""

import scraper_agent.models.schemas as schemas


def test_legacy_page_record_removed() -> None:
    assert not hasattr(schemas, "PageRecord")


def test_legacy_crawl_result_removed() -> None:
    assert not hasattr(schemas, "CrawlResult")


def test_legacy_crawl_metrics_removed() -> None:
    assert not hasattr(schemas, "CrawlMetrics")


def test_public_models_exports() -> None:
    from scraper_agent import models

    assert set(models.__all__) == {"AppConfig", "CrawlRunSummary", "DateRangeConfig"}
