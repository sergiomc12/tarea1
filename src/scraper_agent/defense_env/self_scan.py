"""Self-scan defensivo (Fase exploits) — reusa el catálogo OFENSIVO de
`security_env/` contra la propia infraestructura, en vez de un objetivo
externo. Mismas herramientas, target distinto: qué vería un atacante
externo si escaneara `scraper_agent` (el único servicio con puerto
expuesto al host).

La autorización es efímera y EN MEMORIA (`build_self_scan_guard`), no un
archivo YAML estático: el target real es una IP de Docker resuelta
dinámicamente vía `docker inspect` (`resolve_container_ip`) porque Docker
reasigna direcciones al recrear una red — un CIDR hardcodeado en config se
volvería obsoleto en silencio. Nunca toca `config/authorized_targets.yaml`
(la lista real de objetivos EXTERNOS autorizados por el usuario).

Solo categorías livianas/pasivas (`passive_recon`, `light_active_scan`) --
un self-scan no necesita (ni debería) correr fuzzing o exploits reales
contra la propia infraestructura.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import date
from typing import Protocol

from scraper_agent.security_env.authorization_guard import AuthorizationGuard
from scraper_agent.security_env.exceptions import SecurityEnvError
from scraper_agent.security_env.models import AuthorizedTarget, ToolExecutionRequest
from scraper_agent.security_env.tool_runner import ToolRunner

DEFAULT_SELF_SCAN_TOOLS = ["curl_headers", "nmap_top100", "whatweb_safe"]
SELF_SCAN_CATEGORIES = ["passive_recon", "light_active_scan"]


class _CompletedProcessLike(Protocol):
    stdout: str
    stderr: str
    returncode: int


CommandRunner = Callable[[list[str]], _CompletedProcessLike]


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=30)


def resolve_container_ip(
    container: str,
    network: str,
    *,
    docker_bin: str = "docker",
    runner: CommandRunner = _default_runner,
) -> str:
    """IP real de `container` en `network`, vía `docker inspect` (mismo
    patrón de subprocess que `security_env/docker_executor.py` y
    `container_isolation.py` — sin agregar el SDK de Python de Docker)."""
    fmt = f'{{{{(index .NetworkSettings.Networks "{network}").IPAddress}}}}'
    result = runner([docker_bin, "inspect", container, "--format", fmt])
    ip = (result.stdout or "").strip()
    if not ip:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"no se pudo resolver la IP de {container!r} en la red {network!r}: {stderr}")
    return ip


def build_self_scan_guard(target_ip: str) -> AuthorizationGuard:
    """Autorización efímera en memoria, solo para esta corrida puntual."""
    entry = AuthorizedTarget(
        target=target_ip,
        type="ip",
        authorized_by="defense_env.self_scan",
        authorization_date=date.today(),
        evidence="self-assessment de la propia infraestructura, no un objetivo externo",
        allowed_categories=SELF_SCAN_CATEGORIES,
    )
    return AuthorizationGuard([entry])


async def run_self_scan(
    tool_runner: ToolRunner,
    target_ip: str,
    *,
    tool_ids: list[str] = DEFAULT_SELF_SCAN_TOOLS,
    session_id: str = "self-scan",
) -> list[dict]:
    """Corre cada `tool_id` de `tool_ids` contra `target_ip` con un
    `tool_runner` ya construido (`build_self_scan_guard` para producción,
    `FakeExecutor` para tests). Una herramienta que falla no aborta el resto
    -- el self-scan debe devolver todo lo que sí pudo correr."""
    results: list[dict] = []
    for tool_id in tool_ids:
        try:
            result = await tool_runner.execute(
                ToolExecutionRequest(
                    tool_id=tool_id, host=target_ip, requested_by="self_scan", session_id=session_id
                )
            )
            results.append(
                {
                    "tool_id": tool_id,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout[:2000],
                    "stderr": result.stderr[:500],
                }
            )
        except SecurityEnvError as exc:
            results.append({"tool_id": tool_id, "error": str(exc)})
    return results
