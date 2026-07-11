"""Modelos compartidos de security_env."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ParamType = Literal["hostname", "port", "cidr"]
TargetType = Literal["domain", "ip", "cidr"]


class AuthorizedTarget(BaseModel):
    """Entrada de config/authorized_targets.yaml."""

    target: str
    type: TargetType
    scope: str | None = None
    authorized_by: str
    authorization_date: date
    evidence: str
    expires_at: date | None = None
    allowed_categories: list[str] | None = None
    notes: str | None = None


class AuthorizationResult(BaseModel):
    """Resultado de comprobar autorización."""

    allowed: bool
    reason: str = ""
    matched_target: str | None = None


class ToolParamSpec(BaseModel):
    """Parámetro tipado de una herramienta del catálogo."""

    name: str
    type: ParamType
    required: bool = True


class ToolCatalogEntry(BaseModel):
    """Herramienta permitida en tool_catalog.yaml."""

    id: str
    category: str
    binary: str
    description: str = ""
    timeout_seconds: int = Field(default=60, ge=1, le=900)
    params: list[ToolParamSpec] = Field(default_factory=list)
    argv_template: list[str]


class ToolExecutionRequest(BaseModel):
    """Solicitud de ejecución validada."""

    tool_id: str
    host: str
    params: dict[str, str | int] = Field(default_factory=dict)
    session_id: str = "default"
    requested_by: str = "system"


class CommandResult(BaseModel):
    """Salida de un comando en el runtime."""

    argv: list[str]
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int = 0


class ToolExecutionResult(BaseModel):
    """Resultado expuesto por tool_runner."""

    tool_id: str
    host: str
    category: str
    argv: list[str]
    stdout: str
    stderr: str
    exit_code: int
    allowed: bool = True
    rejection_reason: str | None = None


class AuditLogEntry(BaseModel):
    """Entrada auditable de una ejecución o rechazo."""

    timestamp: datetime
    requested_by: str
    tool_id: str | None
    host: str
    category: str | None
    allowed: bool
    reason: str = ""
    argv: list[str] = Field(default_factory=list)
    exit_code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "requested_by": self.requested_by,
            "tool_id": self.tool_id,
            "host": self.host,
            "category": self.category,
            "allowed": self.allowed,
            "reason": self.reason,
            "argv": self.argv,
            "exit_code": self.exit_code,
        }


class KaliRuntimeSettings(BaseModel):
    """Límites del runtime Kali (ver docs/alcance-seguridad.md §5)."""

    max_runtime_seconds: int = Field(default=300, ge=1)
    max_output_bytes: int = Field(default=5_000_000, ge=1)
    workspace_root: str = "/tmp"

    @field_validator("workspace_root")
    @classmethod
    def _normalize_workspace(cls, value: str) -> str:
        return value.rstrip("/")
