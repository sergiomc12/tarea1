"""Crawl por lotes de todos los medios definidos en sites.yaml."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import yaml

from scraper_agent.crawler.orchestrator import CrawlOrchestrator
from scraper_agent.models.schemas import AppConfig
from scraper_agent.models.search_target import SearchTarget
from scraper_agent.search.persist import write_search_enriched_json
from scraper_agent.storage.html_writer import write_html_report
from scraper_agent.storage.schema_validator import validate_output
from scraper_agent.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MANIFEST = Path("config/sites/sites.yaml")


@dataclass(frozen=True)
class SiteEntry:
    name: str
    config_path: Path
    domain: str


@dataclass
class SiteRunResult:
    name: str
    domain: str
    json_path: Path
    html_path: Path | None
    pages_visited: int
    articles_extracted: int
    schema_ok: bool
    search_hits: int = 0
    error: str | None = None


def load_sites_manifest(manifest_path: Path | str = DEFAULT_MANIFEST) -> list[SiteEntry]:
    """Carga la lista de medios desde config/sites/sites.yaml."""
    path = Path(manifest_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    sites = raw.get("sites") or []
    entries: list[SiteEntry] = []
    for item in sites:
        entries.append(
            SiteEntry(
                name=str(item["name"]),
                config_path=Path(item["config"]),
                domain=str(item["domain"]),
            )
        )
    return entries


def _load_app_config(config_path: Path) -> AppConfig:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(raw)


async def run_site_crawl(
    entry: SiteEntry,
    *,
    date_from,
    date_to,
    ignore_robots: bool,
    search_target: SearchTarget | None = None,
) -> SiteRunResult:
    """Ejecuta crawl de un medio y genera JSON + HTML."""
    cfg = _load_app_config(entry.config_path)
    json_path = Path(cfg.output.path)
    search_hits = 0
    try:
        orchestrator = CrawlOrchestrator(
            cfg,
            ignore_robots=ignore_robots,
            date_from=date_from,
            date_to=date_to,
        )
        summary = await orchestrator.run()
        if search_target and json_path.exists():
            write_search_enriched_json(json_path, search_target)
        html_path = write_html_report(json_path)
        schema_ok = False
        if json_path.exists():
            import json

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            search_hits = len(payload.get("search_results") or [])
            schema_ok = validate_output(payload) == []
        return SiteRunResult(
            name=entry.name,
            domain=entry.domain,
            json_path=json_path,
            html_path=html_path,
            pages_visited=summary.total_pages_visited,
            articles_extracted=summary.total_articles_extracted,
            schema_ok=schema_ok,
            search_hits=search_hits,
        )
    except Exception as exc:
        logger.exception("site_crawl_failed", site=entry.name, error=str(exc))
        return SiteRunResult(
            name=entry.name,
            domain=entry.domain,
            json_path=json_path,
            html_path=None,
            pages_visited=0,
            articles_extracted=0,
            schema_ok=False,
            error=str(exc),
        )


async def run_all_sites(
    manifest_path: Path | str = DEFAULT_MANIFEST,
    *,
    date_from=None,
    date_to=None,
    ignore_robots: bool = False,
) -> list[SiteRunResult]:
    """Crawl secuencial de todos los medios del manifiesto."""
    entries = load_sites_manifest(manifest_path)
    results: list[SiteRunResult] = []
    for entry in entries:
        logger.info("batch_site_start", site=entry.name, domain=entry.domain)
        result = await run_site_crawl(
            entry,
            date_from=date_from,
            date_to=date_to,
            ignore_robots=ignore_robots,
        )
        results.append(result)
        logger.info(
            "batch_site_done",
            site=entry.name,
            articles=result.articles_extracted,
            error=result.error,
        )
    return results


def run_all_sites_sync(
    manifest_path: Path | str = DEFAULT_MANIFEST,
    *,
    date_from=None,
    date_to=None,
    ignore_robots: bool = False,
) -> list[SiteRunResult]:
    return asyncio.run(
        run_all_sites(
            manifest_path,
            date_from=date_from,
            date_to=date_to,
            ignore_robots=ignore_robots,
        )
    )
