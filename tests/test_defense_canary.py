"""Tests de canary files / honeytokens (defense_env/canary.py).

Técnica establecida (mismo principio que canarytokens.org): archivos señuelo
sin ningún uso legítimo -- cualquier interacción con ellos es señal fuerte,
sin los falsos positivos de vigilar un archivo real que a veces cambia
legítimamente. Reusa el motor de FIM (compute_baseline/scan_for_drift) en
vez de reimplementar detección de integridad desde cero.
"""

from __future__ import annotations

from pathlib import Path

from scraper_agent.defense_env.canary import check_canaries, deploy_canaries
from scraper_agent.defense_env.fim import compute_baseline


class TestDeployCanaries:
    def test_creates_decoy_files_with_content(self, tmp_path: Path) -> None:
        locations = [tmp_path / "decoys" / "credentials_backup.yaml"]

        deploy_canaries(locations)

        assert locations[0].exists()
        assert len(locations[0].read_text(encoding="utf-8")) > 0

    def test_idempotent_does_not_overwrite_existing_canary(self, tmp_path: Path) -> None:
        locations = [tmp_path / "decoy.yaml"]
        deploy_canaries(locations)
        original_content = locations[0].read_text(encoding="utf-8")
        locations[0].write_text("contenido tocado por un test previo\n", encoding="utf-8")

        deploy_canaries(locations)

        assert locations[0].read_text(encoding="utf-8") == "contenido tocado por un test previo\n"
        assert locations[0].read_text(encoding="utf-8") != original_content or True  # no se regenera

    def test_returns_watch_config_scoped_to_canary_locations(self, tmp_path: Path) -> None:
        locations = [tmp_path / "a.yaml", tmp_path / "b.yaml"]

        config = deploy_canaries(locations)

        assert set(config.paths) == set(locations)
        assert set(config.critical_files) == {"a.yaml", "b.yaml"}


class TestCheckCanaries:
    def test_no_alerts_when_untouched(self, tmp_path: Path) -> None:
        locations = [tmp_path / "decoy.yaml"]
        config = deploy_canaries(locations)
        baseline = compute_baseline(config)

        alerts = check_canaries(baseline, config)

        assert alerts == []

    def test_modified_canary_raises_critical_alert(self, tmp_path: Path) -> None:
        locations = [tmp_path / "decoy.yaml"]
        config = deploy_canaries(locations)
        baseline = compute_baseline(config)
        locations[0].write_text("alguien lo edito\n", encoding="utf-8")

        alerts = check_canaries(baseline, config)

        assert len(alerts) == 1
        assert alerts[0].severity == "critical"
        assert alerts[0].rule_id == "canary.triggered"
        assert alerts[0].mitre_technique == "T1005"

    def test_deleted_canary_raises_critical_alert(self, tmp_path: Path) -> None:
        locations = [tmp_path / "decoy.yaml"]
        config = deploy_canaries(locations)
        baseline = compute_baseline(config)
        locations[0].unlink()

        alerts = check_canaries(baseline, config)

        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_description_marks_it_explicitly_as_canary(self, tmp_path: Path) -> None:
        locations = [tmp_path / "decoy.yaml"]
        config = deploy_canaries(locations)
        baseline = compute_baseline(config)
        locations[0].write_text("tocado\n", encoding="utf-8")

        alerts = check_canaries(baseline, config)

        assert "Canary disparado" in alerts[0].description
