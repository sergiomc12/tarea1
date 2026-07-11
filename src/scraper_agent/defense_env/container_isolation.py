"""Aislamiento de red de un contenedor comprometido.

Distinto de `active_response.py` (lockdown): el lockdown detiene la
ejecución ofensiva DE `tarea1` mismo (útil si sus propias credenciales
fueron robadas). Esto responde al caso que el lockdown NO cubre --
señalado por el usuario--: un atacante externo comprometiendo la
infraestructura de `tarea1`. La acción es `docker network disconnect` real
sobre el contenedor afectado, vía el mismo `docker.sock` que ya usa
`security_env/docker_executor.py` para `docker exec` (mismo patrón:
subprocess sobre el binario `docker`, no el SDK de Python -- no agrega una
dependencia nueva).

Sin auto-recuperación, a propósito, igual que `clear_lockdown()`: reconectar
requiere una acción humana explícita después de investigar la causa.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


class _CompletedProcessLike(Protocol):
    returncode: int
    stderr: str


CommandRunner = Callable[[list[str]], _CompletedProcessLike]


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=30)


def is_isolated(state_path: Path) -> bool:
    """`True` si el contenedor ya está marcado como aislado."""
    return state_path.exists()


def isolate_container(
    container: str,
    *,
    network: str,
    reason: str,
    state_path: Path,
    docker_bin: str = "docker",
    runner: CommandRunner = _default_runner,
) -> dict:
    """Desconecta `container` de `network`. Idempotente: si ya estaba
    aislado, no vuelve a llamar a `docker` ni pisa el motivo original (la
    primera causa, no la última alerta que llegó mientras se investigaba --
    mismo criterio que `trigger_lockdown`)."""
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))

    result = runner([docker_bin, "network", "disconnect", network, container])
    record = {
        "container": container,
        "network": network,
        "reason": reason,
        "isolated_at": datetime.now(timezone.utc).isoformat(),
        "docker_exit_code": result.returncode,
        "docker_stderr": (result.stderr or "").strip(),
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def reconnect_container(
    container: str,
    *,
    network: str,
    state_path: Path,
    docker_bin: str = "docker",
    runner: CommandRunner = _default_runner,
) -> None:
    """Reconecta `container` a `network` — acción humana explícita. No hace
    nada (ni llama a `docker`) si no había ningún aislamiento activo."""
    if not state_path.exists():
        return
    runner([docker_bin, "network", "connect", network, container])
    state_path.unlink(missing_ok=True)
