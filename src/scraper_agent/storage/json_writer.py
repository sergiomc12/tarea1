"""Persistencia JSON/JSONL y checkpoints (formato scraper-schema.json)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scraper_agent import __version__
from scraper_agent.parser.article_extractor import compute_extraction_quality
from scraper_agent.storage.schema_validator import validate_output
from scraper_agent.utils.logger import get_logger

logger = get_logger(__name__)

ARTICLES_JSONL_NAME = "articles.jsonl"


class JsonWriter:
    """Escritura incremental y consolidación final según scraper-schema.json."""

    def __init__(
        self,
        output_path: str,
        checkpoint_dir: str,
        *,
        incremental: bool = True,
        use_jsonl: bool = False,
    ) -> None:
        self._output_path = Path(output_path)
        self._checkpoint_dir = Path(checkpoint_dir)
        self._incremental = incremental
        self._use_jsonl = use_jsonl
        self._articles: list[dict[str, Any]] = []
        self._article_ids: set[str] = set()
        self._pages_visited = 0
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._jsonl_path = self._output_path.with_suffix(".jsonl")
        self._articles_jsonl_path = self._checkpoint_dir / ARTICLES_JSONL_NAME
        if self._incremental:
            self._load_articles_from_jsonl()

    def _load_articles_from_jsonl(self) -> None:
        if not self._articles_jsonl_path.exists():
            return
        loaded = 0
        for line in self._articles_jsonl_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            article = json.loads(stripped)
            article_id = article.get("article_id")
            if article_id and article_id in self._article_ids:
                continue
            if article_id:
                self._article_ids.add(article_id)
            self._articles.append(article)
            loaded += 1
        if loaded:
            logger.info(
                "incremental_articles_loaded",
                path=str(self._articles_jsonl_path),
                count=loaded,
            )

    def record_page_visit(self) -> None:
        self._pages_visited += 1

    def append_article(self, article: dict[str, Any]) -> None:
        """Añade artículo validado; persiste en JSONL incremental si está activo."""
        article_id = article.get("article_id")
        if article_id and article_id in self._article_ids:
            return
        if article_id:
            self._article_ids.add(article_id)
        self._articles.append(article)
        line = json.dumps(article, ensure_ascii=False) + "\n"
        if self._incremental:
            with self._articles_jsonl_path.open("a", encoding="utf-8") as f:
                f.write(line)
        if self._use_jsonl:
            with self._jsonl_path.open("a", encoding="utf-8") as f:
                f.write(line)

    @property
    def article_count(self) -> int:
        return len(self._articles)

    def save_checkpoint(self, visited: list[str], frontier: list[str]) -> None:
        visited_path = self._checkpoint_dir / "visited_urls.json"
        frontier_path = self._checkpoint_dir / "frontier_queue.json"
        visited_path.write_text(json.dumps(visited, ensure_ascii=False, indent=2), encoding="utf-8")
        frontier_path.write_text(json.dumps(frontier, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_checkpoint(self) -> tuple[list[str], list[str]]:
        visited_path = self._checkpoint_dir / "visited_urls.json"
        frontier_path = self._checkpoint_dir / "frontier_queue.json"
        visited: list[str] = []
        frontier: list[str] = []
        if visited_path.exists():
            visited = json.loads(visited_path.read_text(encoding="utf-8"))
        if frontier_path.exists():
            frontier = json.loads(frontier_path.read_text(encoding="utf-8"))
        return visited, frontier

    def write_final(
        self,
        *,
        crawl_id: str,
        domain: str,
        started_at: datetime,
        robots_txt_respected: bool,
        date_range_filter: dict[str, str | None] | None = None,
        user_agent: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        search_target: dict[str, Any] | None = None,
        search_results: list[dict[str, Any]] | None = None,
    ) -> Path:
        """Escribe JSON final y valida contra scraper-schema.json."""
        finished = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "crawl_metadata": {
                "crawl_id": crawl_id,
                "domain": domain,
                "crawler_version": __version__,
                "crawl_started_at": started_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "crawl_finished_at": finished.isoformat().replace("+00:00", "Z"),
                "total_pages_visited": self._pages_visited,
                "total_articles_extracted": len(self._articles),
                "robots_txt_respected": robots_txt_respected,
                "errors": errors or [],
            },
            "articles": self._articles,
            "extraction_quality": compute_extraction_quality(self._articles),
        }
        if user_agent:
            payload["crawl_metadata"]["user_agent"] = user_agent
        if date_range_filter:
            payload["crawl_metadata"]["date_range_filter"] = date_range_filter
        if search_target:
            payload["crawl_metadata"]["search_target"] = search_target
        if search_results is not None:
            payload["search_results"] = search_results

        validation_errors = validate_output(payload)
        if validation_errors:
            logger.warning("schema_validation_errors", count=len(validation_errors), sample=validation_errors[:3])
        else:
            logger.info("schema_validation_ok")

        self._output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(
            "output_written",
            path=str(self._output_path),
            articles=len(self._articles),
            pages=self._pages_visited,
            incremental_jsonl=str(self._articles_jsonl_path) if self._incremental else None,
        )
        return self._output_path
