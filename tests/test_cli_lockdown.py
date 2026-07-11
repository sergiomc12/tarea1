"""Tests del cableado de Fase 3 (respuesta activa) en la CLI:
auto-lockdown desde fim-scan/defense-correlate + defense-status/-clear-lockdown."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from scraper_agent.cli import app

runner = CliRunner()


def _write_watch_config(tmp_path: Path, watched_dir: Path) -> Path:
    config_path = tmp_path / "fim_watch.yaml"
    config_path.write_text(
        f"paths:\n  - {watched_dir.as_posix()}\n"
        "critical_files:\n  - authorized_targets.yaml\n"
        "exclude_patterns: []\n",
        encoding="utf-8",
    )
    return config_path


def test_fim_scan_critical_alert_auto_creates_case(tmp_path: Path) -> None:
    from scraper_agent.defense_env.cases import list_cases

    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "authorized_targets.yaml").write_text("targets: []\n", encoding="utf-8")
    config_path = _write_watch_config(tmp_path, watched)
    baseline_out = tmp_path / "baseline.json"
    runner.invoke(app, ["fim-baseline", "--config", str(config_path), "--output", str(baseline_out)])
    (watched / "authorized_targets.yaml").write_text("targets:\n  - evil\n", encoding="utf-8")
    cases_path = tmp_path / "cases.json"

    result = runner.invoke(
        app,
        [
            "fim-scan",
            "--config",
            str(config_path),
            "--baseline",
            str(baseline_out),
            "--alerts-out",
            str(tmp_path / "alerts.jsonl"),
            "--lockdown-path",
            str(tmp_path / "LOCKDOWN.json"),
            "--cases-path",
            str(cases_path),
        ],
    )

    assert result.exit_code == 1
    assert "Caso abierto" in result.output
    cases = list_cases(cases_path)
    assert len(cases) == 1
    assert cases[0].severity == "critical"


def test_fim_scan_critical_alert_triggers_lockdown(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "authorized_targets.yaml").write_text("targets: []\n", encoding="utf-8")
    config_path = _write_watch_config(tmp_path, watched)
    baseline_out = tmp_path / "baseline.json"
    runner.invoke(app, ["fim-baseline", "--config", str(config_path), "--output", str(baseline_out)])
    (watched / "authorized_targets.yaml").write_text("targets:\n  - evil\n", encoding="utf-8")
    lockdown_path = tmp_path / "LOCKDOWN.json"

    result = runner.invoke(
        app,
        [
            "fim-scan",
            "--config",
            str(config_path),
            "--baseline",
            str(baseline_out),
            "--alerts-out",
            str(tmp_path / "alerts.jsonl"),
            "--lockdown-path",
            str(lockdown_path),
            "--cases-path",
            str(tmp_path / "cases.json"),
        ],
    )

    assert result.exit_code == 1
    assert lockdown_path.exists()
    assert "LOCKDOWN activado" in result.output


def test_fim_scan_no_auto_lockdown_flag_skips_trigger(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "authorized_targets.yaml").write_text("targets: []\n", encoding="utf-8")
    config_path = _write_watch_config(tmp_path, watched)
    baseline_out = tmp_path / "baseline.json"
    runner.invoke(app, ["fim-baseline", "--config", str(config_path), "--output", str(baseline_out)])
    (watched / "authorized_targets.yaml").write_text("targets:\n  - evil\n", encoding="utf-8")
    lockdown_path = tmp_path / "LOCKDOWN.json"

    runner.invoke(
        app,
        [
            "fim-scan",
            "--config",
            str(config_path),
            "--baseline",
            str(baseline_out),
            "--alerts-out",
            str(tmp_path / "alerts.jsonl"),
            "--lockdown-path",
            str(lockdown_path),
            "--cases-path",
            str(tmp_path / "cases.json"),
            "--no-auto-lockdown",
        ],
    )

    assert not lockdown_path.exists()


def test_defense_status_reports_no_lockdown(tmp_path: Path) -> None:
    result = runner.invoke(app, ["defense-status", "--lockdown-path", str(tmp_path / "LOCKDOWN.json")])

    assert result.exit_code == 0
    assert "Sin lockdown" in result.output


def test_defense_status_reports_active_lockdown(tmp_path: Path) -> None:
    lockdown_path = tmp_path / "LOCKDOWN.json"
    lockdown_path.write_text(
        json.dumps({"reason": "motivo x", "triggered_at": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["defense-status", "--lockdown-path", str(lockdown_path)])

    assert result.exit_code == 1
    assert "motivo x" in result.output


def test_defense_clear_lockdown_requires_confirmation(tmp_path: Path) -> None:
    lockdown_path = tmp_path / "LOCKDOWN.json"
    lockdown_path.write_text(
        json.dumps({"reason": "motivo x", "triggered_at": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["defense-clear-lockdown", "--lockdown-path", str(lockdown_path)])

    assert result.exit_code == 1
    assert lockdown_path.exists()


def test_defense_clear_lockdown_with_confirmation_removes_flag(tmp_path: Path) -> None:
    lockdown_path = tmp_path / "LOCKDOWN.json"
    lockdown_path.write_text(
        json.dumps({"reason": "motivo x", "triggered_at": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["defense-clear-lockdown", "--lockdown-path", str(lockdown_path), "--yes"])

    assert result.exit_code == 0
    assert not lockdown_path.exists()
