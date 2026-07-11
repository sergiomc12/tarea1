"""Tests de export HTML."""

import json
from pathlib import Path

from scraper_agent.storage.html_writer import build_html_document, write_html_report


def test_build_html_document_minimal():
    payload = {
        "crawl_metadata": {
            "crawl_id": "test-1",
            "domain": "gestion.pe",
            "total_articles_extracted": 1,
        },
        "articles": [
            {
                "url": "https://gestion.pe/nota/",
                "headline": {"title": "Titulo de prueba", "subtitle": "Bajada"},
                "dates": {"published_at": "2026-07-05T00:00:00Z"},
                "authorship": {"authors": [{"name": "Autor Test"}]},
                "content_blocks": [
                    {"type": "paragraph", "order": 0, "text": "Primer parrafo."},
                    {
                        "type": "related_link",
                        "order": 1,
                        "text": "Enlace relacionado",
                        "url": "https://gestion.pe/otra/",
                        "label": "LEA TAMBIÉN",
                    },
                ],
            }
        ],
        "extraction_quality": {"confidence_score": 1.0},
    }
    html = build_html_document(payload)
    assert "Titulo de prueba" in html
    assert "Primer parrafo." in html
    assert "Enlace relacionado" in html


def test_write_html_report(tmp_path: Path):
    src = tmp_path / "data.json"
    src.write_text(
        json.dumps(
            {
                "crawl_metadata": {"crawl_id": "x", "domain": "test.pe", "total_articles_extracted": 0},
                "articles": [],
                "extraction_quality": {},
            }
        ),
        encoding="utf-8",
    )
    dest = write_html_report(src)
    assert dest.exists()
    assert dest.suffix == ".html"
