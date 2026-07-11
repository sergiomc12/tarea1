"""Tests del buscador por objetivo profesional."""

import json
from pathlib import Path

from scraper_agent.models.search_target import SearchTarget, load_search_target, merge_search_target
from scraper_agent.search.persist import write_search_enriched_json
from scraper_agent.search.query_engine import apply_search_to_payload, search_articles
from scraper_agent.search.matchers import match_article, normalize_text
from scraper_agent.storage.schema_validator import validate_output


def _article(
    *,
    article_id: str = "art-1",
    title: str = "Gobierno convoca licitación para obra vial",
    excerpt: str = "El proceso de buena pro se realizará en julio",
    paragraphs: list[str] | None = None,
    published_at: str = "2026-07-02T12:00:00Z",
    outbound: list[dict] | None = None,
) -> dict:
    blocks = [
        {"type": "paragraph", "order": idx, "text": text}
        for idx, text in enumerate(paragraphs or ["Detalle de la licitación pública."])
    ]
    return {
        "article_id": article_id,
        "url": "https://gestion.pe/economia/licitacion-noticia",
        "canonical_url": "https://gestion.pe/economia/licitacion-noticia/",
        "amp_url": None,
        "fetch_info": {
            "status_code": 200,
            "fetched_at": "2026-07-06T10:00:00Z",
            "response_time_ms": None,
            "final_url_after_redirects": "https://gestion.pe/economia/licitacion-noticia",
            "html_hash": "sha256:" + "a" * 64,
            "content_length_bytes": 1000,
        },
        "identification": {
            "site_name": "gestion.pe",
            "section": "Economía",
            "subsection": None,
            "breadcrumbs": [],
            "is_premium": False,
            "premium_label": None,
        },
        "headline": {
            "title": title,
            "subtitle": None,
            "kicker": None,
            "meta_title": None,
            "og_title": None,
        },
        "summary": {"excerpt": excerpt},
        "dates": {
            "published_at": published_at,
            "updated_at": None,
            "published_at_raw": None,
            "timezone": "America/Lima",
        },
        "content_blocks": blocks,
        "links": {"outbound_links": outbound or []},
        "authorship": {"authors": [{"name": "Redacción Economía"}]},
        "access": {"is_paywalled": False, "paywall_type": None, "requires_login": False},
    }


def test_normalize_text_strips_accents():
    assert normalize_text("Licitación") == "licitacion"


def test_text_match_in_headline():
    target = SearchTarget(label="licitaciones", keywords=["licitación"])
    matches = match_article(_article(), target)
    assert any(match.field == "headline" for match in matches)
    assert "[[licitación]]" in matches[0].snippet.lower() or "[[licitación]]" in matches[0].snippet


def test_exclude_keyword_discards_article():
    target = SearchTarget(
        label="licitaciones",
        keywords=["licitación"],
        exclude_keywords=["deportes"],
    )
    article = _article(title="Licitación en deportes escolares")
    assert search_articles([article], target) == []


def test_require_all_keywords():
    target = SearchTarget(
        label="licitaciones",
        keywords=["licitación", "buena pro"],
        require_all=True,
        min_score=0.0,
    )
    partial = _article(excerpt="Solo menciona licitación")
    full = _article()
    results = search_articles([partial, full], target)
    assert len(results) == 1
    assert results[0]["article_id"] == "art-1"


def test_pattern_match_in_content():
    target = SearchTarget(
        label="montos",
        patterns=[r"(S/\.\s*[\d,]+)"],
        match_in=["content_blocks"],
        min_score=0.0,
    )
    article = _article(paragraphs=["El monto asciende a S/. 1,500,000"])
    results = search_articles([article], target)
    assert results
    assert "S/." in results[0]["matched_terms"][0]


def test_link_match_in_outbound_links():
    target = SearchTarget(
        label="osce",
        keywords=["osce"],
        match_in=["outbound_links"],
        min_score=0.0,
    )
    article = _article(
        outbound=[{"url": "https://www.osce.gob.pe/licitacion", "anchor_text": "ver en OSCE"}]
    )
    results = search_articles([article], target)
    assert results
    assert "outbound_links" in results[0]["matched_fields"]


def test_date_range_filter_on_target():
    target = SearchTarget(
        label="julio",
        keywords=["licitación"],
        date_range={"from": "2026-07-01", "to": "2026-07-04"},
        min_score=0.0,
    )
    inside = _article(published_at="2026-07-03T10:00:00Z")
    outside = _article(article_id="art-2", published_at="2026-07-10T10:00:00Z")
    results = search_articles([inside, outside], target)
    assert len(results) == 1
    assert results[0]["article_id"] == "art-1"


def test_search_results_sorted_by_score():
    target = SearchTarget(label="licitaciones", keywords=["licitación"], min_score=0.0)
    weak = _article(
        article_id="weak",
        title="Nota breve",
        excerpt="sin palabra clave",
        paragraphs=["licitación al final"],
    )
    strong = _article(article_id="strong", title="licitación licitación licitación")
    results = search_articles([weak, strong], target)
    assert results[0]["article_id"] == "strong"
    assert results[0]["score"] >= results[1]["score"]


def test_apply_search_to_payload_schema_valid():
    payload = {
        "crawl_metadata": {
            "crawl_id": "test-20260706",
            "domain": "gestion.pe",
            "crawler_version": "0.2.0",
            "crawl_started_at": "2026-07-06T10:00:00Z",
            "crawl_finished_at": "2026-07-06T10:05:00Z",
            "total_pages_visited": 1,
            "total_articles_extracted": 1,
            "robots_txt_respected": True,
            "errors": [],
        },
        "articles": [_article()],
        "extraction_quality": {
            "articles_fully_parsed": 1,
            "articles_partial": 0,
            "articles_failed": 0,
            "confidence_score": 1.0,
            "warnings": [],
        },
    }
    target = SearchTarget(label="licitaciones", keywords=["licitación"], min_score=0.0)
    enriched = apply_search_to_payload(payload, target)
    assert enriched["search_results"]
    assert enriched["crawl_metadata"]["search_target"]["label"] == "licitaciones"
    errors = validate_output(enriched)
    assert errors == [], f"schema errors: {errors}"


def test_load_search_target_yaml(tmp_path):
    path = tmp_path / "target.yaml"
    path.write_text(
        """
label: Licitaciones
keywords:
  - licitación
min_score: 0.4
""",
        encoding="utf-8",
    )
    target = load_search_target(path)
    assert target.label == "Licitaciones"
    assert target.min_score == 0.4


def test_merge_search_target_cli_overrides_yaml():
    base = SearchTarget(label="base", keywords=["a"], min_score=0.5)
    merged = merge_search_target(base, keywords=["licitación"], min_score=0.2)
    assert merged.keywords == ["licitación"]
    assert merged.min_score == 0.2
    assert merged.label == "base"


def test_search_match_in_taxonomy():
    target = SearchTarget(
        label="economia",
        keywords=["economía"],
        match_in=["taxonomy"],
        min_score=0.0,
    )
    article = _article(title="Titular neutro", excerpt="sin palabra")
    article["taxonomy"] = {
        "primary_category": "Economía",
        "secondary_categories": [],
        "tags": [],
        "related_topics": [],
    }
    results = search_articles([article], target)
    assert results
    assert "taxonomy" in results[0]["matched_fields"]


def _minimal_crawl_payload(articles: list[dict]) -> dict:
    return {
        "crawl_metadata": {
            "crawl_id": "test-20260706",
            "domain": "gestion.pe",
            "crawler_version": "0.2.0",
            "crawl_started_at": "2026-07-06T10:00:00Z",
            "crawl_finished_at": "2026-07-06T10:05:00Z",
            "total_pages_visited": 1,
            "total_articles_extracted": len(articles),
            "robots_txt_respected": True,
            "errors": [],
        },
        "articles": articles,
        "extraction_quality": {
            "articles_fully_parsed": len(articles),
            "articles_partial": 0,
            "articles_failed": 0,
            "confidence_score": 1.0,
            "warnings": [],
        },
    }


def test_search_from_existing_json_in_place(tmp_path: Path):
    src = tmp_path / "gestion_pe.json"
    src.write_text(json.dumps(_minimal_crawl_payload([_article()]), ensure_ascii=False), encoding="utf-8")
    target = SearchTarget(label="licitaciones", keywords=["licitación"], min_score=0.0)

    write_search_enriched_json(src, target)

    enriched = json.loads(src.read_text(encoding="utf-8"))
    assert enriched["search_results"]
    assert enriched["crawl_metadata"]["search_target"]["label"] == "licitaciones"
    assert validate_output(enriched) == []


def test_search_from_existing_json_to_separate_output(tmp_path: Path):
    src = tmp_path / "gestion_pe.json"
    dest = tmp_path / "busqueda.json"
    src.write_text(json.dumps(_minimal_crawl_payload([_article()]), ensure_ascii=False), encoding="utf-8")
    target = SearchTarget(label="licitaciones", keywords=["licitación"], min_score=0.0)

    write_search_enriched_json(src, target, output_path=dest)

    original = json.loads(src.read_text(encoding="utf-8"))
    assert "search_results" not in original
    enriched = json.loads(dest.read_text(encoding="utf-8"))
    assert enriched["search_results"]
    assert validate_output(enriched) == []


def test_all_predefined_targets_load():
    targets_dir = Path(__file__).resolve().parents[1] / "config" / "targets"
    paths = sorted(targets_dir.glob("*.yaml"))
    assert len(paths) >= 5
    for path in paths:
        target = load_search_target(path)
        assert target.label.strip()
        assert target.keywords or target.patterns
