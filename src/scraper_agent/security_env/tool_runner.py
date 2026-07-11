"""Ejecución controlada de herramientas del catálogo cerrado."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from scraper_agent.security_env.authorization_guard import AuthorizationGuard
from scraper_agent.security_env.exceptions import (
    AuthorizationDenied,
    InvalidToolParams,
    ToolNotFound,
)
from scraper_agent.security_env.kali_runtime import KaliRuntime
from scraper_agent.security_env.models import (
    AuditLogEntry,
    ToolCatalogEntry,
    ToolExecutionRequest,
    ToolExecutionResult,
)
from scraper_agent.security_env.param_validation import (
    build_argv,
    normalize_host,
    validate_cidr,
    validate_hostname,
    validate_tool_params,
)


def default_catalog_path() -> Path:
    return Path(__file__).with_name("tool_catalog.yaml")


def load_tool_catalog(path: Path | str | None = None) -> dict[str, ToolCatalogEntry]:
    catalog_path = Path(path) if path else default_catalog_path()
    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("tool_catalog.yaml debe ser un objeto YAML")
    tools = raw.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("tools debe ser una lista")
    entries = [ToolCatalogEntry.model_validate(item) for item in tools]
    return {entry.id: entry for entry in entries}


class ToolRunner:
    """Orquesta autorización → validación → ejecución en Kali."""

    def __init__(
        self,
        *,
        catalog: dict[str, ToolCatalogEntry],
        guard: AuthorizationGuard,
        runtime: KaliRuntime,
        audit_log: list[AuditLogEntry] | None = None,
        audit_sink_path: Path | None = None,
    ) -> None:
        self._catalog = catalog
        self._guard = guard
        self._runtime = runtime
        self._audit_log = audit_log if audit_log is not None else []
        # Persistencia a disco además del historial en memoria -- sin esto el
        # audit log se perdía al reiniciar el proceso y defense_env/ no tenía
        # ningún log real de ejecuciones/rechazos para correlacionar (gap
        # encontrado en el balance contra Wazuh, ver CHANGELOG.md 2026-07-09).
        self._audit_sink_path = audit_sink_path

    @property
    def audit_log(self) -> list[AuditLogEntry]:
        return self._audit_log

    async def execute(
        self,
        request: ToolExecutionRequest,
        *,
        on: datetime | None = None,
    ) -> ToolExecutionResult:
        now = on or datetime.now(UTC)
        entry = self._catalog.get(request.tool_id)
        if entry is None:
            self._record_audit(
                now=now,
                request=request,
                allowed=False,
                reason=f"herramienta no catalogada: {request.tool_id}",
            )
            raise ToolNotFound(f"herramienta no catalogada: {request.tool_id}")

        host_spec = next((param for param in entry.params if param.name == "host"), None)
        try:
            if host_spec is not None and host_spec.type == "cidr":
                host = validate_cidr(request.host)
            else:
                host = validate_hostname(request.host)
        except InvalidToolParams as exc:
            self._record_audit(
                now=now,
                request=request,
                allowed=False,
                reason=str(exc),
            )
            raise

        auth = self._guard.authorize(host, entry.category, on=now.date())
        if not auth.allowed:
            self._record_audit(
                now=now,
                request=request,
                tool_id=entry.id,
                category=entry.category,
                allowed=False,
                reason=auth.reason,
            )
            raise AuthorizationDenied(auth.reason)

        try:
            validated = validate_tool_params(entry, request.params, host=host)
            argv = build_argv(entry, validated)
        except InvalidToolParams as exc:
            self._record_audit(
                now=now,
                request=request,
                tool_id=entry.id,
                category=entry.category,
                allowed=False,
                reason=str(exc),
            )
            raise

        session = self._runtime.create_session(
            request.session_id,
            allowed_hosts=frozenset({host}),
        )
        command = await session.exec(
            argv,
            target_host=host,
            timeout_seconds=entry.timeout_seconds,
        )
        self._record_audit(
            now=now,
            request=request,
            tool_id=entry.id,
            category=entry.category,
            allowed=True,
            argv=command.argv,
            exit_code=command.exit_code,
        )
        return ToolExecutionResult(
            tool_id=entry.id,
            host=host,
            category=entry.category,
            argv=command.argv,
            stdout=command.stdout,
            stderr=command.stderr,
            exit_code=command.exit_code,
        )

    def _record_audit(
        self,
        *,
        now: datetime,
        request: ToolExecutionRequest,
        allowed: bool,
        reason: str = "",
        tool_id: str | None = None,
        category: str | None = None,
        argv: list[str] | None = None,
        exit_code: int | None = None,
    ) -> None:
        entry = AuditLogEntry(
            timestamp=now,
            requested_by=request.requested_by,
            tool_id=tool_id,
            host=normalize_host(request.host),
            category=category,
            allowed=allowed,
            reason=reason,
            argv=list(argv or []),
            exit_code=exit_code,
        )
        self._audit_log.append(entry)
        if self._audit_sink_path is not None:
            self._audit_sink_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_sink_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry.to_dict(), ensure_ascii=False))
                fh.write("\n")
