"""Validación de fixtures JSON contra scraper-schema.json (contrato de CI)."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scraper_agent.storage.schema_validator import load_schema, validate_output

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _fixture_paths() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.json"))


@pytest.mark.parametrize("fixture_path", _fixture_paths(), ids=lambda p: p.name)
def test_fixture_validates_against_scraper_schema(fixture_path: Path) -> None:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    errors = validate_output(payload)
    assert errors == [], f"{fixture_path.name}: {errors[:5]}"


def test_scraper_schema_is_valid_draft202012() -> None:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)


def test_fixtures_directory_not_empty() -> None:
    paths = _fixture_paths()
    assert len(paths) >= 3, "Se esperan al menos crawl_minimal, crawl_with_search y consolidated_search"
