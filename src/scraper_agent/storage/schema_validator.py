"""Validación contra scraper-schema.json."""

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "scraper-schema.json"


@lru_cache(maxsize=1)
def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_output(payload: dict) -> list[str]:
    """Valida el JSON de salida; retorna lista de errores (vacía = OK)."""
    validator = Draft202012Validator(load_schema())
    return [f"{e.json_path}: {e.message}" for e in validator.iter_errors(payload)]


def validate_article(article: dict) -> list[str]:
    """Valida un artículo individual contra el sub-schema."""
    schema = load_schema()
    wrapped = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        **schema["$defs"]["article"],
    }
    validator = Draft202012Validator(wrapped)
    return [f"{e.json_path}: {e.message}" for e in validator.iter_errors(article)]
