"""Registro auditable de sesiones de chat del agente."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SessionLogEntry(BaseModel):
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    user_message: str = ""
    event_type: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_json_line(self) -> str:
        data = self.model_dump(mode="json")
        return json.dumps(data, ensure_ascii=False)


class SessionLog:
    """Append-only JSONL por sesión."""

    def __init__(self, base_dir: Path | str = "output/sessions") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def append(self, entry: SessionLogEntry) -> Path:
        path = self._base_dir / f"{entry.session_id}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry.to_json_line() + "\n")
        return path

    def read_session(self, session_id: str) -> list[dict[str, Any]]:
        path = self._base_dir / f"{session_id}.jsonl"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
