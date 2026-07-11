"""Cliente HTTP para DeepSeek (chat/completions + tool calls)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from scraper_agent.agent.config import DeepSeekSettings
from scraper_agent.agent.llm_models import (
    TOOL_USE_DOCS_URL,
    TOOL_USE_SUPPORTED,
    AgentOutputMode,
    ChatCompletionResponse,
    ChatMessage,
    JsonPlanAction,
    ToolDefinition,
)
from scraper_agent.agent.tools_schema import tools_as_api_payload


class DeepSeekClient:
    """Wrapper desacoplado del proveedor LLM para security_scraping_agent."""

    def __init__(
        self,
        settings: DeepSeekSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
            },
        )

    @property
    def settings(self) -> DeepSeekSettings:
        return self._settings

    @staticmethod
    def tool_use_capability() -> dict[str, str | bool]:
        """Documenta la decisión del ítem 11 (tool-use confirmado)."""
        return {
            "supported": TOOL_USE_SUPPORTED,
            "mode": "tool_calls",
            "fallback_mode": "json_plan",
            "docs_url": TOOL_USE_DOCS_URL,
            "api_format": "openai_chat_completions",
        }

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
        temperature: float = 0.2,
        stream: bool = False,
    ) -> ChatCompletionResponse:
        if stream:
            raise NotImplementedError("streaming se implementa en api/chat_endpoint (ítem 12)")
        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": [_message_to_api(msg) for msg in messages],
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools_as_api_payload(tools)
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice

        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        return ChatCompletionResponse.model_validate(data)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> DeepSeekClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()


def recommended_output_mode() -> AgentOutputMode:
    """Modo preferido según capacidad confirmada de DeepSeek."""
    return "tool_calls" if TOOL_USE_SUPPORTED else "json_plan"


def parse_json_plan(content: str) -> JsonPlanAction:
    """Fallback: parsea respuesta JSON cuando no hay tool_calls nativos."""
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("respuesta JSON plan invalida") from exc
    if not isinstance(raw, dict):
        raise ValueError("JSON plan debe ser un objeto")
    action = raw.get("action")
    if not isinstance(action, str) or not action.strip():
        raise ValueError("JSON plan requiere campo action")
    arguments = raw.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("JSON plan arguments debe ser objeto")
    return JsonPlanAction(action=action, arguments=arguments)


def _message_to_api(message: ChatMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role}
    if message.content is not None:
        payload["content"] = message.content
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": call.type,
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id:
        payload["tool_call_id"] = message.tool_call_id
    if message.name:
        payload["name"] = message.name
    return payload
