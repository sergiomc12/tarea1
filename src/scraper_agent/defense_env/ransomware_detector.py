"""Detector de patrón ransomware sobre los resultados de un ciclo de FIM.

Señal: N+ archivos MODIFICADOS o BORRADOS en el MISMO ciclo de
`scan_for_drift()` -- comportamiento típico de cifrado/borrado masivo, muy
distinto de una edición manual legítima (que normalmente toca 1 archivo por
vez). No es un motor de comportamiento real (no mira contenido, entropía,
extensiones sospechosas) -- es una heurística simple y honesta sobre una
señal que FIM ya produce, no un reemplazo de un EDR anti-ransomware real.

Limitación explícita: solo ve los paths de `config/defense/fim_watch.yaml`
(hoy: 6 archivos puntuales del propio proyecto), no "la mayoría del
filesystem" -- un ransomware que cifre archivos fuera de esos 6 no dispara
esto. Ver CHANGELOG.md.
"""

from __future__ import annotations

from scraper_agent.defense_env.models import Alert, DriftType

MITRE_DATA_ENCRYPTED_FOR_IMPACT = "T1486"
DEFAULT_THRESHOLD = 5
_MASS_CHANGE_TYPES = {DriftType.MODIFIED, DriftType.DELETED}


def detect_ransomware_pattern(alerts: list[Alert], *, threshold: int = DEFAULT_THRESHOLD) -> Alert | None:
    """`None` si no hay ráfaga; una `Alert` meta `critical` si `threshold` o
    más alertas MODIFIED/DELETED aparecen en el mismo ciclo. Alertas ADDED no
    cuentan -- ransomware cifra/borra, no agrega archivos nuevos."""
    matching = [a for a in alerts if a.drift_type in _MASS_CHANGE_TYPES]
    if len(matching) < threshold:
        return None

    return Alert(
        rule_id="ransomware.mass_file_change",
        severity="critical",
        description=(
            f"{len(matching)} archivos modificados/borrados en el mismo ciclo de FIM "
            "-- patrón de cifrado/borrado masivo, no edición manual normal."
        ),
        mitre_technique=MITRE_DATA_ENCRYPTED_FOR_IMPACT,
        evidence={"affected_files": "; ".join(a.description for a in matching[:10])},
    )
