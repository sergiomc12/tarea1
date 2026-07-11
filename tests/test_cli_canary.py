"""Tests de los comandos CLI defense-canary-deploy / defense-canary-check."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from scraper_agent.cli import app

runner = CliRunner()


def test_deploy_then_check_clean(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    baseline_out = tmp_path / "canary_baseline.json"

    deploy_result = runner.invoke(app, ["defense-canary-deploy", "--baseline-out", str(baseline_out)])
    assert deploy_result.exit_code == 0, deploy_result.output
    assert baseline_out.exists()

    check_result = runner.invoke(
        app,
        [
            "defense-canary-check",
            "--baseline-in",
            str(baseline_out),
            "--alerts-out",
            str(tmp_path / "alerts.jsonl"),
        ],
    )
    assert check_result.exit_code == 0
    assert "Ningún canary fue tocado" in check_result.output


def test_check_detects_tampered_canary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    baseline_out = tmp_path / "canary_baseline.json"
    runner.invoke(app, ["defense-canary-deploy", "--baseline-out", str(baseline_out)])

    canary_path = tmp_path / "output" / "security" / "decoys" / "credentials_backup.yaml"
    canary_path.write_text("tocado por un atacante\n", encoding="utf-8")
    alerts_out = tmp_path / "canary_alerts.jsonl"

    result = runner.invoke(
        app,
        ["defense-canary-check", "--baseline-in", str(baseline_out), "--alerts-out", str(alerts_out)],
    )

    assert result.exit_code == 1
    assert "critical" in result.output
    assert alerts_out.exists()


def test_check_without_baseline_errors_clearly(tmp_path: Path) -> None:
    result = runner.invoke(app, ["defense-canary-check", "--baseline-in", str(tmp_path / "no_existe.json")])

    assert result.exit_code == 2
