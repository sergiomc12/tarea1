"""Tests del detector de patrón ransomware (defense_env/ransomware_detector.py).

Señal: N+ archivos modificados/borrados en el MISMO ciclo de `fim-scan` --
comportamiento típico de cifrado/borrado masivo, distinto de una edición
manual legítima (que normalmente toca 1 archivo por vez). Ver CHANGELOG.md.
"""

from __future__ import annotations

from scraper_agent.defense_env.models import Alert, DriftType
from scraper_agent.defense_env.ransomware_detector import detect_ransomware_pattern


def _alert(drift_type: DriftType, severity: str = "high") -> Alert:
    return Alert(
        rule_id="fim.file_modified",
        severity=severity,
        drift_type=drift_type,
        description="archivo x",
    )


def test_no_alert_when_below_threshold() -> None:
    alerts = [_alert(DriftType.MODIFIED) for _ in range(3)]

    assert detect_ransomware_pattern(alerts, threshold=5) is None


def test_alert_when_at_or_above_threshold() -> None:
    alerts = [_alert(DriftType.MODIFIED) for _ in range(5)]

    result = detect_ransomware_pattern(alerts, threshold=5)

    assert result is not None
    assert result.severity == "critical"
    assert result.rule_id == "ransomware.mass_file_change"
    assert result.mitre_technique == "T1486"


def test_counts_modified_and_deleted_together() -> None:
    alerts = [_alert(DriftType.MODIFIED) for _ in range(3)] + [_alert(DriftType.DELETED) for _ in range(2)]

    result = detect_ransomware_pattern(alerts, threshold=5)

    assert result is not None


def test_added_alerts_do_not_count_toward_threshold() -> None:
    """Archivos NUEVOS no son señal de ransomware (que cifra/borra, no
    agrega). Un despliegue legítimo con varios archivos nuevos no debe
    disparar esto."""
    alerts = [_alert(DriftType.ADDED) for _ in range(10)]

    assert detect_ransomware_pattern(alerts, threshold=5) is None


def test_default_threshold_is_reasonable() -> None:
    # Sin pasar threshold explícito, algo entre 1 y 3 archivos NO debe
    # dispararlo (evita falsos positivos en uso normal).
    alerts = [_alert(DriftType.MODIFIED) for _ in range(2)]

    assert detect_ransomware_pattern(alerts) is None


def test_evidence_includes_affected_file_descriptions() -> None:
    alerts = [_alert(DriftType.MODIFIED) for _ in range(5)]

    result = detect_ransomware_pattern(alerts, threshold=5)

    assert "archivo x" in result.evidence.get("affected_files", "")
