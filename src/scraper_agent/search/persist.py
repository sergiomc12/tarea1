"""Utilidades para persistir resultados de búsqueda."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scraper_agent.models.search_target import SearchTarget
from scraper_agent.search.query_engine import apply_search_to_payload
from scraper_agent.storage.schema_validator import validate_output


def _slugify_label(label: str) -> str:
    folded = label.lower().strip()
    folded = re.sub(r"[^a-z0-9]+", "_", folded)
    return folded.strip("_") or "busqueda"


def enrich_payload_with_search(payload: dict[str, Any], target: SearchTarget) -> dict[str, Any]:
    """Aplica búsqueda y valida contra el schema."""
    enriched = apply_search_to_payload(payload, target)
    errors = validate_output(enriched)
    if errors:
        raise ValueError(f"Salida con search_results invalida: {errors[:3]}")
    return enriched


def write_search_enriched_json(
    json_path: Path | str,
    target: SearchTarget,
    *,
    output_path: Path | str | None = None,
) -> Path:
    """Lee JSON de corrida, aplica búsqueda y reescribe."""
    src = Path(json_path)
    dest = Path(output_path) if output_path else src
    payload = json.loads(src.read_text(encoding="utf-8"))
    enriched = enrich_payload_with_search(payload, target)
    dest.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def write_consolidated_search(
    site_payloads: list[tuple[str, dict[str, Any]]],
    target: SearchTarget,
    output_dir: Path | str = "output",
) -> Path:
    """Consolida search_results de varios sitios en un solo JSON."""
    all_results: list[dict[str, Any]] = []
    for domain, payload in site_payloads:
        for result in payload.get("search_results") or []:
            all_results.append({**result, "domain": domain})
    all_results.sort(key=lambda item: item.get("score", 0), reverse=True)

    consolidated = {
        "crawl_metadata": {
            "crawl_id": f"busqueda-{_slugify_label(target.label)}",
            "domain": "multi-site",
            "crawler_version": site_payloads[0][1]["crawl_metadata"]["crawler_version"]
            if site_payloads
            else "0.2.0",
            "crawl_started_at": site_payloads[0][1]["crawl_metadata"]["crawl_started_at"]
            if site_payloads
            else "",
            "crawl_finished_at": site_payloads[-1][1]["crawl_metadata"]["crawl_finished_at"]
            if site_payloads
            else "",
            "total_pages_visited": sum(
                (payload.get("crawl_metadata") or {}).get("total_pages_visited", 0)
                for _, payload in site_payloads
            ),
            "total_articles_extracted": sum(
                (payload.get("crawl_metadata") or {}).get("total_articles_extracted", 0)
                for _, payload in site_payloads
            ),
            "robots_txt_respected": all(
                (payload.get("crawl_metadata") or {}).get("robots_txt_respected", True)
                for _, payload in site_payloads
            ),
            "errors": [],
            "search_target": target.to_metadata(),
        },
        "articles": [],
        "extraction_quality": {
            "articles_fully_parsed": 0,
            "articles_partial": 0,
            "articles_failed": 0,
            "confidence_score": 1.0 if all_results else 0.0,
            "warnings": [],
        },
        "search_results": all_results,
    }
    dest = Path(output_dir) / f"busqueda_{_slugify_label(target.label)}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    errors = validate_output(consolidated)
    if errors:
        raise ValueError(f"Consolidado invalido: {errors[:3]}")
    dest.write_text(json.dumps(consolidated, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest
