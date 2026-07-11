"""Tests del cableado de detector de ransomware + aislamiento en fim-scan,
y de los comandos defense-isolation-status / defense-reconnect.

IMPORTANTE: estos tests usan `--isolation-container`/`--isolation-network`
apuntando a nombres que NO existen en este host, a propósito -- el CLI
llama al binario real `docker` (sin runner inyectable desde afuera), así
que un nombre real (`scraper_agent`) desconectaría la infraestructura de
verdad como efecto secundario de correr la suite. Con un nombre inexistente,
`docker network disconnect` corre igual pero falla de forma inocua (lo que
también valida que `isolate_container` no explota si docker devuelve error),
y el test verifica el cableado (estado persistido, caso abierto, exit code)
sin tocar nada real.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from scraper_agent.cli import app

runner = CliRunner()

FAKE_CONTAINER = "tarea1-test-no-existe"
FAKE_NETWORK = "tarea1-test-network-no-existe"


def _write_watch_config(tmp_path: Path, watched_dir: Path) -> Path:
    config_path = tmp_path / "fim_watch.yaml"
    config_path.write_text(
        f"paths:\n  - {watched_dir.as_posix()}\ncritical_files: []\nexclude_patterns: []\n",
        encoding="utf-8",
    )
    return config_path


def _isolated_common_args(tmp_path: Path) -> list[str]:
    return [
        "--lockdown-path",
        str(tmp_path / "LOCKDOWN.json"),
        "--cases-path",
        str(tmp_path / "cases.json"),
        "--isolation-path",
        str(tmp_path / "ISOLATED.json"),
        "--isolation-container",
        FAKE_CONTAINER,
        "--isolation-network",
        FAKE_NETWORK,
    ]


def test_fim_scan_mass_change_triggers_isolation(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    for i in range(6):
        (watched / f"file{i}.txt").write_text("original\n", encoding="utf-8")
    config_path = _write_watch_config(tmp_path, watched)
    baseline_out = tmp_path / "baseline.json"
    runner.invoke(app, ["fim-baseline", "--config", str(config_path), "--output", str(baseline_out)])

    for i in range(6):
        (watched / f"file{i}.txt").write_text("CIFRADO_FALSO\n", encoding="utf-8")

    isolation_path = tmp_path / "ISOLATED.json"
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
            *_isolated_common_args(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "ransomware.mass_file_change" in result.output
    assert isolation_path.exists()
    data = json.loads(isolation_path.read_text(encoding="utf-8"))
    assert data["container"] == FAKE_CONTAINER
    assert data["network"] == FAKE_NETWORK


def test_fim_scan_below_threshold_does_not_isolate(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    (watched / "file.txt").write_text("original\n", encoding="utf-8")
    config_path = _write_watch_config(tmp_path, watched)
    baseline_out = tmp_path / "baseline.json"
    runner.invoke(app, ["fim-baseline", "--config", str(config_path), "--output", str(baseline_out)])
    (watched / "file.txt").write_text("cambio unico\n", encoding="utf-8")
    isolation_path = tmp_path / "ISOLATED.json"

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
            *_isolated_common_args(tmp_path),
        ],
    )

    assert not isolation_path.exists()


def test_fim_scan_no_auto_isolate_flag_skips_isolation(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    for i in range(6):
        (watched / f"file{i}.txt").write_text("original\n", encoding="utf-8")
    config_path = _write_watch_config(tmp_path, watched)
    baseline_out = tmp_path / "baseline.json"
    runner.invoke(app, ["fim-baseline", "--config", str(config_path), "--output", str(baseline_out)])
    for i in range(6):
        (watched / f"file{i}.txt").write_text("CIFRADO_FALSO\n", encoding="utf-8")
    isolation_path = tmp_path / "ISOLATED.json"

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
            *_isolated_common_args(tmp_path),
            "--no-auto-isolate",
        ],
    )

    assert result.exit_code == 1  # sigue reportando el patrón, solo no aísla
    assert not isolation_path.exists()


def test_defense_isolation_status_reports_none(tmp_path: Path) -> None:
    result = runner.invoke(app, ["defense-isolation-status", "--isolation-path", str(tmp_path / "x.json")])

    assert result.exit_code == 0
    assert "Sin contenedor aislado" in result.output


def test_defense_isolation_status_reports_active(tmp_path: Path) -> None:
    isolation_path = tmp_path / "ISOLATED.json"
    isolation_path.write_text(
        json.dumps(
            {
                "container": FAKE_CONTAINER,
                "network": FAKE_NETWORK,
                "reason": "motivo x",
                "isolated_at": datetime.now(timezone.utc).isoformat(),
                "docker_exit_code": 1,
                "docker_stderr": "",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["defense-isolation-status", "--isolation-path", str(isolation_path)])

    assert result.exit_code == 1
    assert FAKE_CONTAINER in result.output
    assert "motivo x" in result.output


def test_defense_reconnect_requires_confirmation(tmp_path: Path) -> None:
    isolation_path = tmp_path / "ISOLATED.json"
    isolation_path.write_text(
        json.dumps(
            {
                "container": FAKE_CONTAINER,
                "network": FAKE_NETWORK,
                "reason": "motivo x",
                "isolated_at": datetime.now(timezone.utc).isoformat(),
                "docker_exit_code": 1,
                "docker_stderr": "",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["defense-reconnect", "--isolation-path", str(isolation_path), "--network", FAKE_NETWORK],
    )

    assert result.exit_code == 1
    assert isolation_path.exists()


def test_defense_reconnect_with_confirmation_clears_state(tmp_path: Path) -> None:
    isolation_path = tmp_path / "ISOLATED.json"
    isolation_path.write_text(
        json.dumps(
            {
                "container": FAKE_CONTAINER,
                "network": FAKE_NETWORK,
                "reason": "motivo x",
                "isolated_at": datetime.now(timezone.utc).isoformat(),
                "docker_exit_code": 1,
                "docker_stderr": "",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "defense-reconnect",
            "--isolation-path",
            str(isolation_path),
            "--network",
            FAKE_NETWORK,
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert not isolation_path.exists()
