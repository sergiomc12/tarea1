"""Modelos del protocolo chat/completions (formato OpenAI compatible)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# DeepSeek expone tool calls en /chat/completions (docs: api-docs.deepseek.com/guides/tool_calls).
# deepseek-chat sigue siendo el alias documentado; migrar a deepseek-v4-flash antes de 2026-07-24.
TOOL_USE_SUPPORTED: bool = True
TOOL_USE_DOCS_URL: str = "https://api-docs.deepseek.com/guides/tool_calls"

AgentOutputMode = Literal["tool_calls", "json_plan"]


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ToolFunctionSchema(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    strict: bool | None = None


class ToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: ToolFunctionSchema


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str | None = None


class ChatCompletionResponse(BaseModel):
    id: str = ""
    model: str = ""
    choices: list[ChatCompletionChoice] = Field(default_factory=list)
    usage: ChatCompletionUsage | None = None

    @property
    def assistant_message(self) -> ChatMessage | None:
        if not self.choices:
            return None
        return self.choices[0].message

    @property
    def has_tool_calls(self) -> bool:
        message = self.assistant_message
        return bool(message and message.tool_calls)


class JsonPlanAction(BaseModel):
    """Formato alternativo si tool-use no estuviera disponible (fallback documentado)."""

    action: str
    arguments: dict[str, Any] = Field(default_factory=dict)
