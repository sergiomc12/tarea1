"""Tests del módulo FIM (File Integrity Monitoring) de defense_env."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scraper_agent.defense_env.alert_sink import append_alert, read_alerts
from scraper_agent.defense_env.fim import compute_baseline, missing_watched_paths, scan_for_drift
from scraper_agent.defense_env.models import Alert, DriftType, FimWatchConfig


@pytest.fixture
def watched_dir(tmp_path: Path) -> Path:
    target = tmp_path / "config"
    target.mkdir()
    (target / "authorized_targets.yaml").write_text("targets: []\n", encoding="utf-8")
    (target / "tool_catalog.yaml").write_text("tools: []\n", encoding="utf-8")
    (target / "notes.txt").write_text("no critico\n", encoding="utf-8")
    return target


@pytest.fixture
def watch_config(watched_dir: Path) -> FimWatchConfig:
    return FimWatchConfig(
        paths=[watched_dir],
        critical_files=["authorized_targets.yaml", "tool_catalog.yaml"],
        exclude_patterns=["*.tmp"],
    )


class TestComputeBaseline:
    def test_hashes_every_file_under_watched_paths(self, watch_config: FimWatchConfig) -> None:
        baseline = compute_baseline(watch_config)

        assert set(baseline.keys()) == {
            (watch_config.paths[0] / "authorized_targets.yaml").as_posix(),
            (watch_config.paths[0] / "tool_catalog.yaml").as_posix(),
            (watch_config.paths[0] / "notes.txt").as_posix(),
        }
        entry = baseline[(watch_config.paths[0] / "authorized_targets.yaml").as_posix()]
        assert len(entry.sha256) == 64  # hex digest de SHA-256
        assert entry.size_bytes > 0

    def test_keys_are_platform_independent_posix_style(self, watch_config: FimWatchConfig) -> None:
        """Bug real encontrado corriendo `fim_watcher` en Docker (Linux) contra
        un baseline generado en Windows: `str(Path(...))` usa el separador
        nativo del SO, así que el mismo archivo tenía una clave distinta en
        cada plataforma -- cada archivo aparecía como "borrado" (clave vieja
        con `\\`) Y "agregado" (clave nueva con `/`) al mismo tiempo. Fix:
        las claves siempre usan `.as_posix()` (forward slash), sin importar
        el SO donde corra `fim-baseline` o `fim-scan`. Ver CHANGELOG.md."""
        baseline = compute_baseline(watch_config)

        for key in baseline:
            assert "\\" not in key, f"clave no portable (tiene backslash): {key!r}"

    def test_excludes_paths_matching_exclude_patterns(self, watched_dir: Path, watch_config: FimWatchConfig) -> None:
        (watched_dir / "scratch.tmp").write_text("ignorame\n", encoding="utf-8")

        baseline = compute_baseline(watch_config)

        assert (watched_dir / "scratch.tmp").as_posix() not in baseline

    def test_missing_watched_paths_are_reported_not_silently_skipped(self, tmp_path: Path) -> None:
        """Bug real encontrado en producción: `fim_watcher` corriendo en
        Docker no podía ver `docker-compose.yml`/`docker/` (no montados en
        el contenedor) y `compute_baseline` los salteaba en silencio -- el
        baseline "funcionaba" (3 de 5 archivos) sin ningún aviso de que 2
        rutas configuradas simplemente no existían ahí. Ver CHANGELOG.md."""
        existing = tmp_path / "existe"
        existing.mkdir()
        (existing / "a.yaml").write_text("x: 1\n", encoding="utf-8")
        missing = tmp_path / "no_existe.yaml"
        config = FimWatchConfig(paths=[existing, missing], critical_files=[])

        missing_paths = missing_watched_paths(config)

        assert missing_paths == [missing.as_posix()]

    def test_missing_watched_paths_empty_when_all_exist(self, watch_config: FimWatchConfig) -> None:
        assert missing_watched_paths(watch_config) == []

    def test_empty_watched_dir_returns_empty_baseline(self, tmp_path: Path) -> None:
        empty = tmp_path / "vacio"
        empty.mkdir()
        config = FimWatchConfig(paths=[empty], critical_files=[])

        baseline = compute_baseline(config)

        assert baseline == {}


class TestScanForDrift:
    def test_no_alerts_when_nothing_changed(self, watch_config: FimWatchConfig) -> None:
        baseline = compute_baseline(watch_config)

        alerts = scan_for_drift(baseline, watch_config)

        assert alerts == []

    def test_modified_critical_file_raises_critical_alert(
        self, watched_dir: Path, watch_config: FimWatchConfig
    ) -> None:
        baseline = compute_baseline(watch_config)
        (watched_dir / "authorized_targets.yaml").write_text(
            "targets:\n  - target: evil.example\n", encoding="utf-8"
        )

        alerts = scan_for_drift(baseline, watch_config)

        assert len(alerts) == 1
        assert alerts[0].drift_type == DriftType.MODIFIED
        assert alerts[0].severity == "critical"
        assert (watched_dir / "authorized_targets.yaml").as_posix() in alerts[0].description

    def test_modified_non_critical_file_raises_high_alert(
        self, watched_dir: Path, watch_config: FimWatchConfig
    ) -> None:
        baseline = compute_baseline(watch_config)
        (watched_dir / "notes.txt").write_text("contenido cambiado\n", encoding="utf-8")

        alerts = scan_for_drift(baseline, watch_config)

        assert len(alerts) == 1
        assert alerts[0].drift_type == DriftType.MODIFIED
        assert alerts[0].severity == "high"

    def test_new_file_raises_medium_added_alert(self, watched_dir: Path, watch_config: FimWatchConfig) -> None:
        baseline = compute_baseline(watch_config)
        (watched_dir / "nuevo_archivo.yaml").write_text("x: 1\n", encoding="utf-8")

        alerts = scan_for_drift(baseline, watch_config)

        assert len(alerts) == 1
        assert alerts[0].drift_type == DriftType.ADDED
        assert alerts[0].severity == "medium"

    def test_deleted_file_raises_high_alert(self, watched_dir: Path, watch_config: FimWatchConfig) -> None:
        baseline = compute_baseline(watch_config)
        (watched_dir / "tool_catalog.yaml").unlink()

        alerts = scan_for_drift(baseline, watch_config)

        assert len(alerts) == 1
        assert alerts[0].drift_type == DriftType.DELETED
        assert alerts[0].severity == "critical"

    def test_multiple_drifts_all_reported(self, watched_dir: Path, watch_config: FimWatchConfig) -> None:
        baseline = compute_baseline(watch_config)
        (watched_dir / "notes.txt").write_text("cambio\n", encoding="utf-8")
        (watched_dir / "tool_catalog.yaml").unlink()
        (watched_dir / "nuevo.yaml").write_text("y: 2\n", encoding="utf-8")

        alerts = scan_for_drift(baseline, watch_config)

        assert len(alerts) == 3
        drift_types = {a.drift_type for a in alerts}
        assert drift_types == {DriftType.MODIFIED, DriftType.DELETED, DriftType.ADDED}

    def test_alerts_carry_mitre_technique_for_critical_files(
        self, watched_dir: Path, watch_config: FimWatchConfig
    ) -> None:
        baseline = compute_baseline(watch_config)
        (watched_dir / "authorized_targets.yaml").write_text("targets: []\nx: 1\n", encoding="utf-8")

        alerts = scan_for_drift(baseline, watch_config)

        assert alerts[0].mitre_technique == "T1565"


class TestAlertSink:
    def test_append_and_read_round_trip(self, tmp_path: Path) -> None:
        sink_path = tmp_path / "alerts.jsonl"
        alert = Alert(
            rule_id="fim.critical_file_modified",
            severity="critical",
            drift_type=DriftType.MODIFIED,
            description="config/authorized_targets.yaml modificado",
            mitre_technique="T1565",
        )

        append_alert(alert, sink_path)
        append_alert(alert, sink_path)
        loaded = read_alerts(sink_path)

        assert len(loaded) == 2
        assert loaded[0].rule_id == "fim.critical_file_modified"
        assert loaded[0].severity == "critical"

    def test_read_alerts_on_missing_file_returns_empty_list(self, tmp_path: Path) -> None:
        assert read_alerts(tmp_path / "no_existe.jsonl") == []

    def test_append_writes_valid_jsonl(self, tmp_path: Path) -> None:
        sink_path = tmp_path / "alerts.jsonl"
        alert = Alert(
            rule_id="fim.file_added",
            severity="medium",
            drift_type=DriftType.ADDED,
            description="archivo nuevo",
        )

        append_alert(alert, sink_path)

        lines = sink_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["rule_id"] == "fim.file_added"
