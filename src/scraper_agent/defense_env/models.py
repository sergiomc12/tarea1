"""Modelos compartidos de defense_env."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]


class DriftType(StrEnum):
    """Tipo de cambio detectado por el scan de FIM contra el baseline."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    PERMISSIONS_CHANGED = "permissions_changed"


class FimBaselineEntry(BaseModel):
    """Estado conocido-bueno de un archivo vigilado."""

    path: str
    sha256: str
    size_bytes: int
    mtime: float


class FimWatchConfig(BaseModel):
    """Config de qué vigilar (`config/defense/fim_watch.yaml`)."""

    paths: list[Path] = Field(default_factory=list)
    critical_files: list[str] = Field(
        default_factory=list,
        description="Nombres de archivo (basename) que disparan severidad critical si cambian.",
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Patrones fnmatch a excluir del baseline (ej. '*.tmp').",
    )


class Alert(BaseModel):
    """Alerta emitida por cualquier detector de defense_env (FIM, motor de
    correlación). `drift_type` es específico de FIM y queda `None` para
    alertas del motor de correlación (`rule_id` identifica el origen)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rule_id: str
    severity: Severity
    drift_type: DriftType | None = None
    description: str
    mitre_technique: str | None = None
    evidence: dict[str, str] = Field(default_factory=dict)


class CorrelationRule(BaseModel):
    """Regla de correlación tipo Sigma simplificado (YAML, filtro de campos +
    umbral de frecuencia opcional). Ver `defense_env/correlation.py` y
    `defense_env/rules/builtin/*.yaml`."""

    id: str
    title: str
    severity: Severity
    logsource: str
    filter: dict[str, object] = Field(
        default_factory=dict,
        description="Igualdad exacta por campo; una lista de valores significa 'campo in lista'.",
    )
    group_by: str | None = None
    threshold_count: int = Field(default=1, ge=1)
    window_seconds: int = Field(default=300, ge=1)
    description: str = ""
    mitre_technique: str | None = None


CaseStatus = Literal["open", "investigating", "closed"]


class Case(BaseModel):
    """Investigación que agrupa una o más alertas — equivalente acotado a un
    caso de TheHive (Fase 4). Ver `defense_env/cases.py`."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    status: CaseStatus = "open"
    severity: Severity
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    alert_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
