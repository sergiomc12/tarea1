"""Tests de gestión de casos (Fase 4, defense_env/cases.py) — equivalente
acotado a TheHive: agrupar alertas en investigaciones abiertas/cerradas en
vez de solo emitirlas a un JSONL crudo."""

from __future__ import annotations

from pathlib import Path

from scraper_agent.defense_env.cases import (
    add_note,
    auto_create_case_from_alert,
    close_case,
    create_case,
    list_cases,
)
from scraper_agent.defense_env.models import Alert, DriftType


def _critical_alert() -> Alert:
    return Alert(
        rule_id="fim.file_modified",
        severity="critical",
        drift_type=DriftType.MODIFIED,
        description="config/authorized_targets.yaml modificado",
    )


class TestCreateAndListCases:
    def test_create_case_persists_to_store(self, tmp_path: Path) -> None:
        store = tmp_path / "cases.json"

        case = create_case(store, title="Investigar alerta X", severity="high", alert_ids=["a1"])

        assert case.status == "open"
        cases = list_cases(store)
        assert len(cases) == 1
        assert cases[0].id == case.id

    def test_list_cases_filters_by_status(self, tmp_path: Path) -> None:
        store = tmp_path / "cases.json"
        create_case(store, title="Caso 1", severity="low", alert_ids=[])
        c2 = create_case(store, title="Caso 2", severity="high", alert_ids=[])
        close_case(store, c2.id)

        open_cases = list_cases(store, status="open")
        closed_cases = list_cases(store, status="closed")

        assert len(open_cases) == 1
        assert len(closed_cases) == 1
        assert closed_cases[0].id == c2.id

    def test_list_cases_on_empty_store_returns_empty(self, tmp_path: Path) -> None:
        assert list_cases(tmp_path / "no_existe.json") == []


class TestCloseAndAnnotate:
    def test_close_case_updates_status(self, tmp_path: Path) -> None:
        store = tmp_path / "cases.json"
        case = create_case(store, title="X", severity="medium", alert_ids=[])

        closed = close_case(store, case.id, note="falso positivo, config editada a mano")

        assert closed.status == "closed"
        assert "falso positivo, config editada a mano" in closed.notes

    def test_add_note_appends_without_changing_status(self, tmp_path: Path) -> None:
        store = tmp_path / "cases.json"
        case = create_case(store, title="X", severity="medium", alert_ids=[])

        updated = add_note(store, case.id, "revisando con el equipo")

        assert updated.status == "open"
        assert updated.notes == ["revisando con el equipo"]

    def test_close_unknown_case_id_raises(self, tmp_path: Path) -> None:
        store = tmp_path / "cases.json"
        create_case(store, title="X", severity="low", alert_ids=[])

        import pytest

        with pytest.raises(KeyError):
            close_case(store, "no-existe")


class TestAutoCreateFromAlert:
    def test_critical_alert_auto_creates_case(self, tmp_path: Path) -> None:
        store = tmp_path / "cases.json"
        alert = _critical_alert()

        case = auto_create_case_from_alert(store, alert)

        assert case is not None
        assert case.severity == "critical"
        assert alert.id in case.alert_ids
        assert list_cases(store) == [case]

    def test_non_critical_alert_does_not_auto_create_case(self, tmp_path: Path) -> None:
        store = tmp_path / "cases.json"
        alert = Alert(
            rule_id="fim.file_added",
            severity="medium",
            drift_type=DriftType.ADDED,
            description="archivo nuevo",
        )

        case = auto_create_case_from_alert(store, alert)

        assert case is None
        assert list_cases(store) == []
