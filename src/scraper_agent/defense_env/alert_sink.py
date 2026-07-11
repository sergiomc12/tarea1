"""Persistencia de alertas en JSONL — mismo patrón que `output/sessions/*.jsonl`
del agente LLM, por consistencia con el resto del proyecto."""

from __future__ import annotations

import json
from pathlib import Path

from scraper_agent.defense_env.models import Alert


def append_alert(alert: Alert, path: Path) -> None:
    """Agrega `alert` como una línea JSON a `path` (crea el archivo/carpeta si falta)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(alert.model_dump_json())
        fh.write("\n")


def read_alerts(path: Path) -> list[Alert]:
    """Lee todas las alertas persistidas en `path`. Devuelve `[]` si no existe."""
    if not path.exists():
        return []
    alerts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            alerts.append(Alert.model_validate(json.loads(line)))
    return alerts
