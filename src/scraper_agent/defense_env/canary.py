"""Canary files (honeytokens) — señal de posible fuga de información.

Técnica establecida (mismo principio que canarytokens.org): archivos señuelo
con contenido de cebo realista y CERO uso legítimo. Cualquier interacción
con ellos (modificado, movido, borrado) es una señal fuerte, sin los falsos
positivos que tendría vigilar un archivo real que a veces cambia
legítimamente. Reusa el motor de FIM (`fim.compute_baseline`/
`fim.scan_for_drift`) en vez de reimplementar detección de integridad desde
cero — un canary es, técnicamente, un `FimWatchConfig` de scope reducido con
contenido señuelo.

Limitación honesta: la señal es MODIFICACIÓN/BORRADO/MOVIDO (mismo mecanismo
que FIM, hash+existencia). NO hay detección de solo-lectura (nadie puede
"copiar y leer sin tocar" un archivo sin que esto lo note) — eso requeriría
confiar en `atime`, que muchos filesystems/montajes (`noatime`, overlay de
Docker, NTFS por defecto) no actualizan de forma confiable en cada lectura.
Se evaluó y se descartó a propósito antes de implementar algo que diera una
falsa sensación de cobertura. Ver CHANGELOG.md.
"""

from __future__ import annotations

from pathlib import Path

from scraper_agent.defense_env.fim import scan_for_drift
from scraper_agent.defense_env.models import Alert, FimBaselineEntry, FimWatchConfig

MITRE_DATA_FROM_LOCAL_SYSTEM = "T1005"


def _decoy_content(name: str) -> str:
    return (
        "# ARCHIVO DE RESPALDO INTERNO -- NO COMPARTIR\n"
        "# generado automáticamente para uso operativo\n"
        "authorized_targets_backup:\n"
        "  - target: internal-prod-db.example.local\n"
        "    credentials_ref: vault://prod/db-master\n"
        "  - target: billing-api.example.local\n"
        "    credentials_ref: vault://prod/billing-key\n"
    )


def deploy_canaries(locations: list[Path]) -> FimWatchConfig:
    """Crea un archivo señuelo en cada ruta de `locations` (si no existe
    todavía — idempotente, no pisa un canary ya desplegado ni lo que le
    hayan tocado) y devuelve el `FimWatchConfig` con scope reducido a esos
    paths, listo para `fim.compute_baseline()`."""
    for location in locations:
        if not location.exists():
            location.parent.mkdir(parents=True, exist_ok=True)
            location.write_text(_decoy_content(location.name), encoding="utf-8")
    return FimWatchConfig(paths=list(locations), critical_files=[p.name for p in locations])


def check_canaries(baseline: dict[str, FimBaselineEntry], config: FimWatchConfig) -> list[Alert]:
    """Cualquier drift sobre un canary es evidencia de que algo/alguien
    interactuó con un archivo que nunca debería tocarse -- a diferencia de
    FIM normal (donde un archivo agregado es solo "medium"), acá TODO drift
    es `critical` sin excepción: un canary no tiene ningún cambio legítimo
    posible."""
    raw_alerts = scan_for_drift(baseline, config)
    return [
        Alert(
            rule_id="canary.triggered",
            severity="critical",
            drift_type=alert.drift_type,
            description=f"Canary disparado: {alert.description}",
            mitre_technique=MITRE_DATA_FROM_LOCAL_SYSTEM,
            evidence=alert.evidence,
        )
        for alert in raw_alerts
    ]
