"""Tests de los comandos CLI defense-remediate-suggest / defense-remediate-apply."""

from __future__ import annotations

from typer.testing import CliRunner

from scraper_agent.cli import app

runner = CliRunner()


def test_suggest_never_applies() -> None:
    result = runner.invoke(app, ["defense-remediate-suggest", "outdated_openssh", "--package-manager", "dnf"])

    assert result.exit_code == 0
    assert "NO se aplicó" in result.output
    assert "dnf update -y openssh-server" in result.output


def test_suggest_unknown_pattern() -> None:
    result = runner.invoke(app, ["defense-remediate-suggest", "no-existe"])

    assert result.exit_code == 1
    assert "Sin sugerencia" in result.output


def test_apply_without_yes_refuses() -> None:
    result = runner.invoke(app, ["defense-remediate-apply", "outdated_openssh"])

    assert result.exit_code == 1
    assert "No se aplicó" in result.output
