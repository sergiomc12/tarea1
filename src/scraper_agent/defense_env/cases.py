"""Gestión de casos (Fase 4) — equivalente acotado a TheHive: agrupar
alertas en investigaciones abiertas/cerradas en vez de solo emitirlas a un
JSONL crudo que nadie vuelve a mirar. Almacenamiento: un único JSON
(`output/security/cases.json`, lista de `Case`) leído/reescrito completo en
cada operación — suficiente al volumen de alertas que genera este proyecto
hoy; si eso cambia, el primer paso sería paginar o mover a SQLite, no
reescribir esto desde cero.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scraper_agent.defense_env.models import Alert, Case, Severity


def _load(store_path: Path) -> list[Case]:
    if not store_path.exists():
        return []
    raw = json.loads(store_path.read_text(encoding="utf-8"))
    return [Case.model_validate(item) for item in raw]


def _save(store_path: Path, cases: list[Case]) -> None:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [case.model_dump(mode="json") for case in cases]
    store_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def list_cases(store_path: Path, *, status: str | None = None) -> list[Case]:
    """Lista casos, opcionalmente filtrados por `status`."""
    cases = _load(store_path)
    if status is not None:
        cases = [c for c in cases if c.status == status]
    return cases


def create_case(store_path: Path, *, title: str, severity: Severity, alert_ids: list[str]) -> Case:
    """Crea un caso nuevo y lo persiste."""
    cases = _load(store_path)
    case = Case(title=title, severity=severity, alert_ids=list(alert_ids))
    cases.append(case)
    _save(store_path, cases)
    return case


def _mutate(store_path: Path, case_id: str, mutator) -> Case:
    cases = _load(store_path)
    for i, case in enumerate(cases):
        if case.id == case_id:
            updated = mutator(case)
            updated.updated_at = datetime.now(timezone.utc)
            cases[i] = updated
            _save(store_path, cases)
            return updated
    raise KeyError(f"No existe un caso con id {case_id!r}")


def close_case(store_path: Path, case_id: str, *, note: str = "") -> Case:
    """Marca un caso como `closed`. `note` (opcional) queda registrada."""

    def _close(case: Case) -> Case:
        case.status = "closed"
        if note:
            case.notes.append(note)
        return case

    return _mutate(store_path, case_id, _close)


def add_note(store_path: Path, case_id: str, note: str) -> Case:
    """Agrega una nota sin cambiar el status."""

    def _annotate(case: Case) -> Case:
        case.notes.append(note)
        return case

    return _mutate(store_path, case_id, _annotate)


def auto_create_case_from_alert(store_path: Path, alert: Alert) -> Case | None:
    """Crea un caso automáticamente SOLO para alertas `critical` — el resto
    queda en el JSONL de alertas crudo, visible pero sin abrir una
    investigación por cada evento de severidad menor (eso sería ruido, no
    gestión de casos)."""
    if alert.severity != "critical":
        return None
    return create_case(
        store_path,
        title=f"[{alert.rule_id}] {alert.description}",
        severity=alert.severity,
        alert_ids=[alert.id],
    )
