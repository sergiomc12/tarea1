"""Respuesta activa (Fase 3): un circuit breaker fail-closed, no acciones
destructivas ni auto-modificación de `authorized_targets.yaml`.

Cuando una alerta `critical` dispara `trigger_lockdown()`, se escribe un
archivo flag en disco; mientras exista, `AuthorizationGuard.authorize()`
(ver `security_env/authorization_guard.py`) deniega TODA ejecución
ofensiva, sin importar si el target/categoría normalmente estarían
autorizados. Solo un humano lo limpia (`clear_lockdown()`) — no hay
auto-recuperación, a propósito: un lockdown que se levanta solo no protege
de nada.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def is_locked_down(path: Path) -> bool:
    """`True` si hay un lockdown activo (el archivo flag existe)."""
    return path.exists()


def trigger_lockdown(reason: str, path: Path) -> None:
    """Activa el lockdown con `reason`. Si ya había uno activo, NO lo
    sobreescribe — se conserva el motivo original (la primera causa, no la
    última alerta que llegó mientras alguien investigaba)."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"reason": reason, "triggered_at": datetime.now(timezone.utc).isoformat()},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def read_lockdown_reason(path: Path) -> str | None:
    """Motivo del lockdown activo, o `None` si no hay ninguno."""
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("reason")


def clear_lockdown(path: Path) -> None:
    """Levanta el lockdown (acción humana explícita). No falla si ya no existe."""
    path.unlink(missing_ok=True)
