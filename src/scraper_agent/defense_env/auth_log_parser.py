"""Parser de logs de autenticación SSH — RHEL/CentOS: `/var/log/secure`;
Debian/Ubuntu: `/var/log/auth.log`. Convierte líneas de syslog de `sshd`
en eventos que el motor de correlación EXISTENTE (`correlation.py`) ya
sabe procesar (`evaluate_rule`/`run_correlation`, umbral + ventana
deslizante) — no se reimplementa detección de fuerza bruta desde cero.

Formato esperado (syslog estándar de sshd):
    "Mon DD HH:MM:SS host sshd[PID]: Failed password for [invalid user] USER from IP port PORT ssh2"
    "Mon DD HH:MM:SS host sshd[PID]: Accepted password for USER from IP port PORT ssh2"

LIMITACIÓN HONESTA (ver CHANGELOG.md): el syslog tradicional NO incluye el
año en el timestamp — se asume el año actual (o el que se pase
explícitamente vía `year=`). Si el log cruza un cambio de año, los
timestamps del tramo anterior quedarían mal calculados; no se implementó
detección automática de ese caso. Tampoco verificado contra un
`/var/log/secure` real (mismo entorno Windows sin Linux real de esta
sesión) — verificar el formato exacto en el servidor real antes de confiar
en esto en producción.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

_SSH_LINE_RE = re.compile(
    r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+sshd\[(?P<pid>\d+)\]:\s+"
    r"(?P<status>Failed password|Accepted password)\s+for\s+"
    r"(?:invalid user\s+)?(?P<user>\S+)\s+from\s+(?P<ip>[\d.]+)\s+port\s+(?P<port>\d+)"
)

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_ssh_auth_line(line: str, *, year: int | None = None) -> dict | None:
    """`None` si la línea no matchea un intento de login SSH conocido."""
    match = _SSH_LINE_RE.match(line.strip())
    if not match:
        return None
    month = _MONTHS.get(match.group("month"))
    if month is None:
        return None
    resolved_year = year if year is not None else datetime.now(timezone.utc).year
    day = int(match.group("day"))
    hh, mm, ss = (int(x) for x in match.group("time").split(":"))
    timestamp = datetime(resolved_year, month, day, hh, mm, ss, tzinfo=timezone.utc)
    return {
        "timestamp": timestamp.isoformat(),
        "allowed": match.group("status") == "Accepted password",
        "user": match.group("user"),
        "source_ip": match.group("ip"),
        "port": int(match.group("port")),
    }


def parse_ssh_auth_log(path: Path, *, year: int | None = None) -> list[dict]:
    """Parsea todas las líneas de `path` que matcheen un intento de login
    SSH. `[]` si el archivo no existe."""
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        event = parse_ssh_auth_line(line, year=year)
        if event is not None:
            events.append(event)
    return events
