"""Tests de los comandos CLI de gestión de casos (Fase 4)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from scraper_agent.cli import app

runner = CliRunner()


def test_case_create_then_list(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.json"

    create_result = runner.invoke(
        app, ["defense-case-create", "Investigar drift sospechoso", "--cases-path", str(cases_path)]
    )
    assert create_result.exit_code == 0, create_result.output

    list_result = runner.invoke(app, ["defense-case-list", "--cases-path", str(cases_path)])
    assert list_result.exit_code == 0
    assert "Investigar drift sospechoso" in list_result.output
    assert "[open]" in list_result.output


def test_case_list_empty_store(tmp_path: Path) -> None:
    result = runner.invoke(app, ["defense-case-list", "--cases-path", str(tmp_path / "no_existe.json")])

    assert result.exit_code == 0
    assert "Sin casos" in result.output


def test_case_close_by_id_prefix(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.json"
    runner.invoke(app, ["defense-case-create", "Caso a cerrar", "--cases-path", str(cases_path)])
    from scraper_agent.defense_env.cases import list_cases

    case_id = list_cases(cases_path)[0].id

    result = runner.invoke(
        app,
        [
            "defense-case-close",
            case_id[:8],
            "--note",
            "resuelto",
            "--cases-path",
            str(cases_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert list_cases(cases_path, status="closed")[0].notes == ["resuelto"]


def test_case_close_unknown_id_fails(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["defense-case-close", "no-existe", "--cases-path", str(tmp_path / "cases.json")]
    )

    assert result.exit_code == 1
