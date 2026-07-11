"""Modelo de objetivo de búsqueda profesional."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from scraper_agent.models.schemas import DateRangeConfig

DEFAULT_MATCH_FIELDS = (
    "headline",
    "excerpt",
    "content_blocks",
    "outbound_links",
    "authors",
    "taxonomy",
)

VALID_MATCH_FIELDS = frozenset(DEFAULT_MATCH_FIELDS)


class SearchTarget(BaseModel):
    """Encapsula lo que el usuario quiere encontrar en una corrida."""

    model_config = ConfigDict(populate_by_name=True)

    label: str = "busqueda"
    keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    match_in: list[str] = Field(default_factory=lambda: list(DEFAULT_MATCH_FIELDS))
    min_score: float = Field(default=0.3, ge=0.0, le=1.0)
    require_all: bool = False
    date_range: DateRangeConfig | None = None

    @field_validator("match_in")
    @classmethod
    def _validate_match_in(cls, value: list[str]) -> list[str]:
        if not value:
            return list(DEFAULT_MATCH_FIELDS)
        invalid = [field for field in value if field not in VALID_MATCH_FIELDS]
        if invalid:
            raise ValueError(f"match_in invalido: {invalid}")
        return value

    def to_metadata(self) -> dict[str, Any]:
        """Serializa para crawl_metadata.search_target."""
        payload: dict[str, Any] = {
            "label": self.label,
            "keywords": self.keywords,
            "exclude_keywords": self.exclude_keywords,
            "patterns": self.patterns,
            "match_in": self.match_in,
            "min_score": self.min_score,
            "require_all": self.require_all,
        }
        if self.date_range:
            payload["date_range"] = {
                "from": self.date_range.from_date,
                "to": self.date_range.to_date,
            }
        return payload


def load_search_target(path: Path | str) -> SearchTarget:
    """Carga objetivo desde YAML (`config/targets/<nombre>.yaml`)."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("target-file debe ser un objeto YAML")
    return SearchTarget.model_validate(raw)


def merge_search_target(
    base: SearchTarget | None,
    *,
    label: str | None = None,
    keywords: list[str] | None = None,
    exclude_keywords: list[str] | None = None,
    patterns: list[str] | None = None,
    match_in: list[str] | None = None,
    min_score: float | None = None,
    require_all: bool | None = None,
    date_range: DateRangeConfig | None = None,
) -> SearchTarget:
    """Combina objetivo YAML con flags CLI (CLI gana sobre YAML)."""
    data = base.model_dump() if base else {}
    if label is not None:
        data["label"] = label
    if keywords is not None:
        data["keywords"] = keywords
    if exclude_keywords is not None:
        data["exclude_keywords"] = exclude_keywords
    if patterns is not None:
        data["patterns"] = patterns
    if match_in is not None:
        data["match_in"] = match_in
    if min_score is not None:
        data["min_score"] = min_score
    if require_all is not None:
        data["require_all"] = require_all
    if date_range is not None:
        data["date_range"] = date_range
    return SearchTarget.model_validate(data)
