"""Remediación de vulnerabilidades — REGLA DURA de `defense_env/` (ver
CHANGELOG.md): toda acción de remediación (parchear, cambiar
configuración) SIEMPRE informa, sugiere la solución exacta, y exige
confirmación humana explícita antes de aplicar. Nunca auto-aplica, sin
excepción.

Distinto de la contención rápida (`active_response.trigger_lockdown`,
`container_isolation.isolate_container`, el `block_ip` automático de
`host_agent.py` ante fuerza bruta SSH) — esas siguen siendo automáticas a
propósito, porque son reflejos de emergencia que no pueden esperar una
confirmación humana sin dejar avanzar el ataque. Remediar (cambiar el
sistema para arreglar la causa) es una decisión distinta, nunca urgente
en el mismo sentido, y siempre reversible-o-no de forma menos predecible
— por eso acá la regla es la opuesta: nunca sin humano.

`apply_remediation()` rechaza ESTRUCTURALMENTE (`ValueError`, no una
convención de CLI) cualquier intento de aplicar sin `confirmed=True`
explícito — imposible de saltear llamando la función distinto.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


class _CompletedProcessLike(Protocol):
    stdout: str
    stderr: str
    returncode: int


CommandRunner = Callable[[list[str]], _CompletedProcessLike]


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=60)


@dataclass
class RemediationSuggestion:
    id: str
    issue: str
    explanation: str
    suggested_command: list[str]
    risk_level: str  # "low" | "medium" | "high"
    source: str


_RemediationBuilder = Callable[[dict], RemediationSuggestion]
_KNOWN_REMEDIATIONS: dict[str, _RemediationBuilder] = {}


def _register(pattern_id: str) -> Callable[[_RemediationBuilder], _RemediationBuilder]:
    def _decorator(fn: _RemediationBuilder) -> _RemediationBuilder:
        _KNOWN_REMEDIATIONS[pattern_id] = fn
        return fn

    return _decorator


@_register("outdated_openssh")
def _outdated_openssh(finding: dict) -> RemediationSuggestion:
    pkg_manager = finding.get("package_manager", "dnf")
    return RemediationSuggestion(
        id="outdated_openssh",
        issue=f"OpenSSH desactualizado detectado: {finding.get('detail', '(sin detalle)')}",
        explanation=(
            "Versión de OpenSSH con CVEs conocidos según el banner detectado "
            "(self-scan/nmap). Actualizar el paquete a la última versión del "
            "repositorio de la distro."
        ),
        suggested_command=[pkg_manager, "update", "-y", "openssh-server"],
        risk_level="medium",
        source=finding.get("source", "self-scan"),
    )


@_register("weak_sshd_config")
def _weak_sshd_config(finding: dict) -> RemediationSuggestion:
    setting = finding.get("setting", "PermitRootLogin")
    return RemediationSuggestion(
        id="weak_sshd_config",
        issue=f"Configuración insegura en sshd_config: {setting} {finding.get('current_value', '')}".strip(),
        explanation=(
            "Esta configuración facilita fuerza bruta o acceso no autorizado "
            "por SSH. Se sugiere desactivarla (revisar que no rompa un flujo "
            "de acceso legítimo antes de aplicar)."
        ),
        suggested_command=["sed", "-i", f"s/^{setting}.*/{setting} no/", "/etc/ssh/sshd_config"],
        risk_level="high",
        source=finding.get("source", "host_fim"),
    )


def suggest_remediation(pattern_id: str, finding: dict) -> RemediationSuggestion | None:
    """`None` si `pattern_id` no es un patrón reconocido -- nunca se
    inventa una sugerencia para algo que no se conoce (peor dar un
    comando incorrecto que no dar ninguno)."""
    builder = _KNOWN_REMEDIATIONS.get(pattern_id)
    if builder is None:
        return None
    return builder(finding)


def apply_remediation(suggestion: RemediationSuggestion, *, confirmed: bool, runner: CommandRunner = _default_runner) -> dict:
    """Aplica `suggestion.suggested_command` — SOLO si `confirmed=True`
    explícito. Regla dura: rechaza con `ValueError` en cualquier otro
    caso, sin llamar al `runner` (cero efectos secundarios si no se
    confirmó)."""
    if not confirmed:
        raise ValueError(
            "apply_remediation requiere confirmed=True explícito — nunca se "
            "aplica una remediación sin confirmación humana (regla dura de defense_env/, ver CHANGELOG.md)"
        )
    result = runner(suggestion.suggested_command)
    return {
        "suggestion_id": suggestion.id,
        "command": suggestion.suggested_command,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "success": result.returncode == 0,
        "detail": (result.stderr or result.stdout or "").strip(),
    }
