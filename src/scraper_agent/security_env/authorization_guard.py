"""Verificación de objetivos autorizados antes de ejecutar herramientas."""

from __future__ import annotations

import ipaddress
import json
from datetime import date
from fnmatch import fnmatch
from pathlib import Path

import yaml

from scraper_agent.security_env.exceptions import AuthorizationDenied
from scraper_agent.security_env.models import AuthorizationResult, AuthorizedTarget
from scraper_agent.security_env.param_validation import normalize_host


def load_authorized_targets(path: Path | str) -> list[AuthorizedTarget]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("authorized_targets.yaml debe ser un objeto YAML")
    entries = raw.get("authorized_targets", [])
    if not isinstance(entries, list):
        raise ValueError("authorized_targets debe ser una lista")
    return [AuthorizedTarget.model_validate(item) for item in entries]


class AuthorizationGuard:
    """Comprueba autorización según docs/alcance-seguridad.md §4."""

    def __init__(self, entries: list[AuthorizedTarget], *, lockdown_path: Path | None = None) -> None:
        self.entries = entries
        # Fase 3 de defense_env/ (respuesta activa): si está seteado y el
        # archivo flag existe, `authorize()` deniega TODO antes de mirar
        # `entries` — circuit breaker fail-closed disparado por una alerta
        # crítica (ver defense_env/active_response.py). `None` (default)
        # deja el comportamiento anterior sin cambios.
        self._lockdown_path = lockdown_path

    def authorize(
        self,
        host: str,
        category: str,
        *,
        on: date | None = None,
    ) -> AuthorizationResult:
        if self._lockdown_path is not None and self._lockdown_path.exists():
            reason = json.loads(self._lockdown_path.read_text(encoding="utf-8")).get("reason", "")
            return AuthorizationResult(
                allowed=False,
                reason=f"lockdown activo ({reason}) — ver defense_env/active_response.py",
            )
        normalized = normalize_host(host)
        today = on or date.today()
        for entry in self.entries:
            if not self._host_matches_entry(normalized, entry):
                continue
            if entry.expires_at is not None and entry.expires_at < today:
                return AuthorizationResult(
                    allowed=False,
                    reason=f"autorizacion expirada para {entry.target}",
                    matched_target=entry.target,
                )
            if entry.allowed_categories and category not in entry.allowed_categories:
                return AuthorizationResult(
                    allowed=False,
                    reason=f"categoria {category!r} no permitida para {entry.target}",
                    matched_target=entry.target,
                )
            return AuthorizationResult(
                allowed=True,
                reason="autorizado",
                matched_target=entry.target,
            )
        return AuthorizationResult(
            allowed=False,
            reason=f"objetivo {normalized!r} no autorizado en authorized_targets.yaml",
        )

    def require(self, host: str, category: str, *, on: date | None = None) -> AuthorizationResult:
        result = self.authorize(host, category, on=on)
        if not result.allowed:
            raise AuthorizationDenied(result.reason)
        return result

    def _host_matches_entry(self, host: str, entry: AuthorizedTarget) -> bool:
        target = normalize_host(entry.target)
        if entry.type == "ip":
            return host == target
        if entry.type == "cidr":
            try:
                network = ipaddress.ip_network(entry.target, strict=False)
            except ValueError:
                return False
            try:
                return ipaddress.ip_address(host) in network
            except ValueError:
                try:
                    host_net = ipaddress.ip_network(host, strict=False)
                except ValueError:
                    return False
                return host_net == network or host_net.subnet_of(network)
        if host == target:
            return True
        if entry.scope:
            pattern = entry.scope
            if pattern.startswith("*."):
                suffix = pattern[2:]
                return host == suffix or host.endswith(f".{suffix}")
            return fnmatch(host, pattern)
        return False
