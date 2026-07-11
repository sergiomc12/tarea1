"""Tests del comando CLI defense-host-agent-cycle."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from scraper_agent.cli import app

runner = CliRunner()


def _write_fim_config(tmp_path: Path, watched_dir: Path) -> Path:
    config_path = tmp_path / "host_fim_watch.yaml"
    config_path.write_text(
        f"paths:\n  - {watched_dir.as_posix()}\ncritical_files: []\nexclude_patterns: []\n",
        encoding="utf-8",
    )
    return config_path


def test_cycle_clean_state_exits_zero(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    config_path = _write_fim_config(tmp_path, watched)
    ssh_log = tmp_path / "secure"
    ssh_log.write_text("", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "defense-host-agent-cycle",
            "--fim-config",
            str(config_path),
            "--fim-baseline",
            str(tmp_path / "baseline.json"),
            "--ssh-auth-log",
            str(ssh_log),
            "--cases-path",
            str(tmp_path / "cases.json"),
            "--no-auto-identify",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "0 alerta" in result.output


def test_cycle_missing_config_errors_clearly(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["defense-host-agent-cycle", "--fim-config", str(tmp_path / "no_existe.yaml")],
    )

    assert result.exit_code == 2
