"""Defensa activa a nivel de SISTEMA OPERATIVO Linux (servidor real, ej.
CentOS/RHEL) — distinto de todo el resto de `defense_env/`, que actúa
sobre contenedores Docker propios de `tarea1`. Esto actúa sobre el host.

Auto-detecta el sistema operativo (`/etc/os-release`, estándar en toda
distro Linux moderna) y qué herramienta de firewall está REALMENTE
instalada en ese host (no asume una fija) — prioridad `firewalld` (default
en RHEL/CentOS 7+) → `nftables` → `iptables`. Acciones: `block_ip`,
`close_port`, `kill_process`, `list_connections` — las que el usuario pidió
explícitamente ("cerrar puerto y cerrar conexión, matar aplicaciones").

LIMITACIÓN HONESTA (ver CHANGELOG.md): desarrollado en un entorno Windows
sin acceso a un CentOS/RHEL real — testeado con runners falsos (mismo
patrón que el resto de `defense_env/`), NO verificado contra
infraestructura real como sí se hizo con las piezas basadas en Docker.
Correr `defense-host-detect` en el servidor real antes de confiar en esto.

RIESGO: estas acciones corren con privilegios de root/sudo sobre el
sistema operativo real de producción, no un contenedor descartable. Sin
reversión automática — un humano deshace la regla de firewall a mano.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


class _CompletedProcessLike(Protocol):
    stdout: str
    stderr: str
    returncode: int


CommandRunner = Callable[[list[str]], _CompletedProcessLike]


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=30)


def _command_exists(binary: str, runner: CommandRunner) -> bool:
    result = runner(["which", binary])
    return result.returncode == 0 and bool((result.stdout or "").strip())


@dataclass
class OSInfo:
    id: str = "unknown"
    id_like: str = ""
    name: str = "unknown"
    version_id: str = ""
    is_linux: bool = False


def detect_os(*, os_release_path: Path = Path("/etc/os-release")) -> OSInfo:
    """Parsea `/etc/os-release`. Si no existe (ej. corriendo en Windows
    durante desarrollo), devuelve `is_linux=False` en vez de fallar --
    permite que el resto del código chequee esto explícitamente antes de
    intentar cualquier acción destructiva."""
    if not os_release_path.exists():
        return OSInfo(is_linux=False)
    fields: dict[str, str] = {}
    for line in os_release_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip().strip('"')
    return OSInfo(
        id=fields.get("ID", "unknown"),
        id_like=fields.get("ID_LIKE", ""),
        name=fields.get("NAME", "unknown"),
        version_id=fields.get("VERSION_ID", ""),
        is_linux=True,
    )


@dataclass
class FirewallTool:
    name: str  # "firewalld" | "nftables" | "iptables" | "none"
    binary: str


def detect_firewall_tool(*, runner: CommandRunner = _default_runner) -> FirewallTool:
    """Prioridad: `firewalld` (default RHEL/CentOS 7+) → `nftables` →
    `iptables`. Detecta cuál está REALMENTE disponible en este host en vez
    de asumir una herramienta fija -- el usuario pidió explícitamente esto
    ("no tengo la lista de qué puede haber como herramientas")."""
    if _command_exists("firewall-cmd", runner):
        return FirewallTool(name="firewalld", binary="firewall-cmd")
    if _command_exists("nft", runner):
        return FirewallTool(name="nftables", binary="nft")
    if _command_exists("iptables", runner):
        return FirewallTool(name="iptables", binary="iptables")
    return FirewallTool(name="none", binary="")


@dataclass
class ActionResult:
    action: str
    target: str
    tool_used: str
    success: bool
    detail: str
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _no_tool_result(action: str, target: str) -> ActionResult:
    return ActionResult(
        action=action,
        target=target,
        tool_used="none",
        success=False,
        detail="no se detectó ninguna herramienta de firewall en este host (firewalld/nftables/iptables)",
    )


def block_ip(ip: str, *, firewall: FirewallTool, runner: CommandRunner = _default_runner) -> ActionResult:
    """Bloquea todo el tráfico entrante de `ip` ("cerrar conexión") con la
    herramienta de firewall detectada."""
    if firewall.name == "firewalld":
        result = runner(["firewall-cmd", "--permanent", "--zone=drop", f"--add-source={ip}"])
        if result.returncode == 0:
            runner(["firewall-cmd", "--reload"])
    elif firewall.name == "nftables":
        result = runner(["nft", "add", "rule", "inet", "filter", "input", "ip", "saddr", ip, "drop"])
    elif firewall.name == "iptables":
        result = runner(["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"])
    else:
        return _no_tool_result("block_ip", ip)

    return ActionResult(
        action="block_ip",
        target=ip,
        tool_used=firewall.name,
        success=result.returncode == 0,
        detail=(result.stderr or result.stdout or "").strip(),
    )


def close_port(
    port: int, *, protocol: str = "tcp", firewall: FirewallTool, runner: CommandRunner = _default_runner
) -> ActionResult:
    """Cierra `port` ("cerrar puerto") con la herramienta de firewall detectada."""
    target = f"{port}/{protocol}"
    if firewall.name == "firewalld":
        result = runner(["firewall-cmd", "--permanent", f"--remove-port={target}"])
        if result.returncode == 0:
            runner(["firewall-cmd", "--reload"])
    elif firewall.name == "nftables":
        result = runner(["nft", "add", "rule", "inet", "filter", "input", protocol, "dport", str(port), "drop"])
    elif firewall.name == "iptables":
        result = runner(["iptables", "-I", "INPUT", "-p", protocol, "--dport", str(port), "-j", "DROP"])
    else:
        return _no_tool_result("close_port", target)

    return ActionResult(
        action="close_port",
        target=target,
        tool_used=firewall.name,
        success=result.returncode == 0,
        detail=(result.stderr or result.stdout or "").strip(),
    )


def kill_process(*, pid: int | None = None, name: str | None = None, runner: CommandRunner = _default_runner) -> ActionResult:
    """Mata un proceso por `pid` (`kill -9`) o por `name` (`pkill -9 -f`,
    coincide contra la línea de comando completa). Se necesita exactamente
    uno de los dos."""
    if pid is None and not name:
        raise ValueError("se necesita pid o name")
    if pid is not None:
        result = runner(["kill", "-9", str(pid)])
        target = f"pid:{pid}"
    else:
        result = runner(["pkill", "-9", "-f", name])  # type: ignore[list-item]
        target = f"name:{name}"

    return ActionResult(
        action="kill_process",
        target=target,
        tool_used="kill/pkill",
        success=result.returncode == 0,
        detail=(result.stderr or "").strip(),
    )


def list_connections(*, runner: CommandRunner = _default_runner) -> list[dict]:
    """Conexiones de red activas -- `ss` preferido sobre `netstat`
    (`netstat` está deprecado en distros RHEL/CentOS modernas; `ss` de
    `iproute2` es el reemplazo estándar). Devuelve líneas crudas para
    revisión humana -- no se implementó un parser estructurado columna por
    columna porque el formato de salida no se pudo verificar contra un
    RHEL real en este entorno de desarrollo (ver limitación en el
    docstring del módulo); un parser "aproximado" sin verificar sería peor
    que ninguno."""
    if _command_exists("ss", runner):
        result = runner(["ss", "-tunp"])
    elif _command_exists("netstat", runner):
        result = runner(["netstat", "-tunp"])
    else:
        return []

    lines = (result.stdout or "").splitlines()
    return [{"raw": line.strip()} for line in lines[1:] if line.strip()]
