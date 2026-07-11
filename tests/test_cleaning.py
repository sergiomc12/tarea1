"""Tests de limpieza."""

from scraper_agent.cleaning.deduplicator import Deduplicator
from scraper_agent.cleaning.normalizer import clean_text, normalize_record


def test_clean_text():
    assert clean_text("  hola&nbsp; mundo  ") == "hola mundo"


def test_normalize_record():
    data = normalize_record({"t": "  x  ", "n": [1, 2]})
    assert data["t"] == "x"
    assert data["n"] == [1, 2]


def test_deduplicator():
    dedup = Deduplicator()
    assert dedup.is_duplicate("https://a.com", {"k": "v"}) is False
    assert dedup.is_duplicate("https://a.com", {"k": "v"}) is True
