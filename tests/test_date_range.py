"""Tests del filtro por intervalo de fechas."""

from datetime import datetime, timezone

from scraper_agent.parser.article_extractor import article_in_date_range


def _article(pub: str) -> dict:
    return {"dates": {"published_at": pub}}


def test_inclusive_continuous_range():
    date_from = datetime(2026, 7, 1, tzinfo=timezone.utc)
    date_to = datetime(2026, 7, 4, 23, 59, 59, tzinfo=timezone.utc)

    assert article_in_date_range(_article("2026-07-01T00:00:00Z"), date_from, date_to)
    assert article_in_date_range(_article("2026-07-04T23:59:59Z"), date_from, date_to)
    assert article_in_date_range(_article("2026-07-02T12:00:00Z"), date_from, date_to)


def test_outside_range_excluded():
    date_from = datetime(2026, 7, 1, tzinfo=timezone.utc)
    date_to = datetime(2026, 7, 4, 23, 59, 59, tzinfo=timezone.utc)

    assert not article_in_date_range(_article("2026-06-30T23:59:59Z"), date_from, date_to)
    assert not article_in_date_range(_article("2026-07-05T00:00:00Z"), date_from, date_to)


def test_open_ended_range():
    date_from = datetime(2026, 7, 1, tzinfo=timezone.utc)

    assert article_in_date_range(_article("2026-08-01T00:00:00Z"), date_from, None)
    assert not article_in_date_range(_article("2026-06-01T00:00:00Z"), date_from, None)


def test_no_filter_includes_all():
    assert article_in_date_range(_article("2026-01-01T00:00:00Z"), None, None)
