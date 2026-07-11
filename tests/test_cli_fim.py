"""Tests de los comandos CLI fim-baseline / fim-scan."""

from __future__ import annotations

import json
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


def test_fim_baseline_creates_baseline_file(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "authorized_targets.yaml").write_text("targets: []\n", encoding="utf-8")
    config_path = _write_watch_config(tmp_path, watched)
    baseline_out = tmp_path / "baseline.json"

    result = runner.invoke(
        app, ["fim-baseline", "--config", str(config_path), "--output", str(baseline_out)]
    )

    assert result.exit_code == 0, result.output
    assert baseline_out.exists()
    data = json.loads(baseline_out.read_text(encoding="utf-8"))
    assert len(data) == 1


def test_fim_scan_exits_zero_when_no_drift(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "authorized_targets.yaml").write_text("targets: []\n", encoding="utf-8")
    config_path = _write_watch_config(tmp_path, watched)
    baseline_out = tmp_path / "baseline.json"
    runner.invoke(app, ["fim-baseline", "--config", str(config_path), "--output", str(baseline_out)])

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
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Sin drift" in result.output


def test_fim_scan_exits_nonzero_when_critical_drift(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "authorized_targets.yaml").write_text("targets: []\n", encoding="utf-8")
    config_path = _write_watch_config(tmp_path, watched)
    baseline_out = tmp_path / "baseline.json"
    runner.invoke(app, ["fim-baseline", "--config", str(config_path), "--output", str(baseline_out)])
    (watched / "authorized_targets.yaml").write_text("targets:\n  - evil\n", encoding="utf-8")
    alerts_out = tmp_path / "alerts.jsonl"

    result = runner.invoke(
        app,
        [
            "fim-scan",
            "--config",
            str(config_path),
            "--baseline",
            str(baseline_out),
            "--alerts-out",
            str(alerts_out),
            # Fase 3/4 disparan lockdown + caso automático en alerta critical
            # (comportamiento correcto en producción) — sin aislar estas
            # rutas acá, el test escribe en el output/security/ REAL del
            # proyecto en vez de en tmp_path. Gap real encontrado corriendo
            # este mismo test tras agregar las fases 3/4, ver CHANGELOG.md.
            "--lockdown-path",
            str(tmp_path / "LOCKDOWN.json"),
            "--cases-path",
            str(tmp_path / "cases.json"),
        ],
    )

    assert result.exit_code == 1
    assert "critical" in result.output
    assert alerts_out.exists()
    lines = alerts_out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_fim_scan_without_baseline_errors_clearly(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    config_path = _write_watch_config(tmp_path, watched)

    result = runner.invoke(
        app,
        [
            "fim-scan",
            "--config",
            str(config_path),
            "--baseline",
            str(tmp_path / "no_existe.json"),
        ],
    )

    assert result.exit_code != 0
    assert "baseline" in result.output.lower()
