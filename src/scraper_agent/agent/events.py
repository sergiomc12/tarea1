"""Eventos emitidos por el agente orquestador (streaming SSE)."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentEventType(StrEnum):
    STATUS = "status"
    ASSISTANT_DELTA = "assistant_delta"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    FINAL = "final"
    ERROR = "error"


class AgentEvent(BaseModel):
    type: AgentEventType
    data: dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        payload = json.dumps({"type": self.type, "data": self.data}, ensure_ascii=False)
        return f"event: {self.type}\ndata: {payload}\n\n"
