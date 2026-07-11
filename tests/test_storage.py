"""Tests de almacenamiento."""

import json
from datetime import datetime, timezone
from pathlib import Path

from scraper_agent.storage.json_writer import JsonWriter
from scraper_agent.storage.schema_validator import validate_output


def _sample_article(article_id: str = "gestion-abc123") -> dict:
    return {
        "article_id": article_id,
        "url": f"https://gestion.pe/nota/{article_id}/",
        "canonical_url": f"https://gestion.pe/nota/{article_id}/",
        "amp_url": None,
        "fetch_info": {
            "status_code": 200,
            "fetched_at": "2026-07-04T18:00:00Z",
            "response_time_ms": None,
            "final_url_after_redirects": f"https://gestion.pe/nota/{article_id}/",
            "html_hash": "sha256:" + "a" * 64,
            "content_length_bytes": 1000,
        },
        "identification": {
            "site_name": "gestion.pe",
            "section": "Economia",
            "subsection": None,
            "breadcrumbs": [],
            "is_premium": False,
            "premium_label": None,
        },
        "headline": {"title": "Titulo", "subtitle": None, "kicker": None, "meta_title": None, "og_title": None},
        "dates": {
            "published_at": "2026-07-04T18:00:00Z",
            "updated_at": None,
            "published_at_raw": None,
            "timezone": "America/Lima",
        },
        "content_blocks": [{"type": "paragraph", "order": 0, "text": "Cuerpo"}],
        "access": {"is_paywalled": False, "paywall_type": None, "requires_login": False},
    }


def test_json_writer_schema_output(tmp_path: Path):
    out = tmp_path / "out.json"
    ckpt = tmp_path / "ckpt"
    writer = JsonWriter(str(out), str(ckpt))
    writer.record_page_visit()
    writer.append_article(_sample_article())
    path = writer.write_final(
        crawl_id="gestion-test",
        domain="gestion.pe",
        started_at=datetime(2026, 7, 4, tzinfo=timezone.utc),
        robots_txt_respected=True,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["crawl_metadata"]["total_articles_extracted"] == 1
    errors = validate_output(payload)
    assert errors == []


def test_incremental_writes_articles_jsonl_sidecar(tmp_path: Path):
    out = tmp_path / "out.json"
    ckpt = tmp_path / "ckpt"
    writer = JsonWriter(str(out), str(ckpt), incremental=True)
    writer.append_article(_sample_article("a1"))
    writer.append_article(_sample_article("a2"))

    jsonl_path = ckpt / "articles.jsonl"
    assert jsonl_path.exists()
    lines = [ln for ln in jsonl_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    assert json.loads(lines[0])["article_id"] == "a1"


def test_incremental_reloads_articles_on_resume(tmp_path: Path):
    out = tmp_path / "out.json"
    ckpt = tmp_path / "ckpt"
    writer1 = JsonWriter(str(out), str(ckpt), incremental=True)
    writer1.append_article(_sample_article("resume-1"))
    writer1.append_article(_sample_article("resume-2"))
    assert writer1.article_count == 2

    writer2 = JsonWriter(str(out), str(ckpt), incremental=True)
    assert writer2.article_count == 2
    writer2.append_article(_sample_article("resume-3"))
    assert writer2.article_count == 3

    path = writer2.write_final(
        crawl_id="gestion-test",
        domain="gestion.pe",
        started_at=datetime(2026, 7, 4, tzinfo=timezone.utc),
        robots_txt_respected=True,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["crawl_metadata"]["total_articles_extracted"] == 3
    ids = {a["article_id"] for a in payload["articles"]}
    assert ids == {"resume-1", "resume-2", "resume-3"}


def test_incremental_dedupes_by_article_id(tmp_path: Path):
    out = tmp_path / "out.json"
    ckpt = tmp_path / "ckpt"
    writer = JsonWriter(str(out), str(ckpt), incremental=True)
    writer.append_article(_sample_article("dup"))
    writer.append_article(_sample_article("dup"))

    assert writer.article_count == 1
    lines = [ln for ln in (ckpt / "articles.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1


def test_incremental_disabled_skips_jsonl_sidecar(tmp_path: Path):
    out = tmp_path / "out.json"
    ckpt = tmp_path / "ckpt"
    writer = JsonWriter(str(out), str(ckpt), incremental=False)
    writer.append_article(_sample_article("no-jsonl"))

    assert not (ckpt / "articles.jsonl").exists()
    assert writer.article_count == 1
