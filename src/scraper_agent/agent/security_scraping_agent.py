"""Agente orquestador scraping + seguridad vía DeepSeek tool calls."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from scraper_agent.agent.events import AgentEvent, AgentEventType
from scraper_agent.agent.llm_client import DeepSeekClient, parse_json_plan, recommended_output_mode
from scraper_agent.agent.llm_models import ChatMessage, ToolCall
from scraper_agent.agent.tool_handlers import AgentDependencies, ToolHandlerRegistry
from scraper_agent.agent.tools_schema import build_agent_tools
from scraper_agent.storage.session_log import SessionLog, SessionLogEntry
from scraper_agent.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """Eres un agente que orquesta scraping de noticias peruanas y testing de seguridad controlado.

Reglas:
- Para scraping usa run_site_crawl o search_crawl_output.
- Para herramientas Kali usa run_security_tool solo contra hosts autorizados.
- Explica brevemente qué harás antes de ejecutar tools.
- Resume resultados en español claro; incluye datos clave del JSON de tool.
- Nunca sugieras exploits, brute force ni bypass de WAF.
"""

MAX_TOOL_ROUNDS = 5


class SecurityScrapingAgent:
    """Interpreta instrucciones naturales y ejecuta tools con trazabilidad."""

    def __init__(
        self,
        llm: DeepSeekClient,
        *,
        handlers: ToolHandlerRegistry | None = None,
        session_log: SessionLog | None = None,
        deps: AgentDependencies | None = None,
    ) -> None:
        self._llm = llm
        self._deps = deps or AgentDependencies()
        self._handlers = handlers or ToolHandlerRegistry(self._deps)
        self._session_log = session_log or SessionLog()
        self._tools = build_agent_tools()

    async def run_stream(
        self,
        user_message: str,
        *,
        session_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        sid = session_id or str(uuid.uuid4())
        self._deps.session_id = sid
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_message),
        ]
        self._log(sid, user_message, "user_message", {"message": user_message})
        yield AgentEvent(type=AgentEventType.STATUS, data={"message": "Analizando instrucción..."})

        try:
            async for event in self._agent_loop(messages, sid):
                yield event
        except Exception as exc:
            logger.exception("agent_error", session_id=sid)
            self._log(sid, user_message, "error", {"detail": str(exc)})
            yield AgentEvent(type=AgentEventType.ERROR, data={"message": str(exc)})

    async def _agent_loop(
        self,
        messages: list[ChatMessage],
        session_id: str,
    ) -> AsyncIterator[AgentEvent]:
        for round_idx in range(MAX_TOOL_ROUNDS):
            response = await self._llm.chat_completion(messages, tools=self._tools)
            assistant = response.assistant_message
            if assistant is None:
                yield AgentEvent(
                    type=AgentEventType.ERROR,
                    data={"message": "Respuesta vacía del LLM"},
                )
                return

            if assistant.tool_calls:
                messages.append(assistant)
                for call in assistant.tool_calls:
                    async for event in self._execute_tool_call(call, messages, session_id):
                        yield event
                continue

            content = assistant.content or ""
            if content and recommended_output_mode() == "json_plan" and content.strip().startswith("{"):
                plan = parse_json_plan(content)
                yield AgentEvent(
                    type=AgentEventType.TOOL_START,
                    data={"tool": plan.action, "arguments": plan.arguments},
                )
                result = await self._handlers.dispatch_json_plan(plan)
                yield AgentEvent(
                    type=AgentEventType.TOOL_END,
                    data={"tool": plan.action, "result": result},
                )
                messages.append(ChatMessage(role="assistant", content=content))
                messages.append(
                    ChatMessage(role="user", content=f"Resultado tool: {result}. Resume para el usuario.")
                )
                continue

            if content:
                yield AgentEvent(type=AgentEventType.ASSISTANT_DELTA, data={"content": content})
                self._log(session_id, "", "assistant_final", {"content": content, "round": round_idx})
                yield AgentEvent(type=AgentEventType.FINAL, data={"content": content})
                return

        yield AgentEvent(
            type=AgentEventType.ERROR,
            data={"message": f"Límite de {MAX_TOOL_ROUNDS} rondas de tools alcanzado"},
        )

    async def _execute_tool_call(
        self,
        call: ToolCall,
        messages: list[ChatMessage],
        session_id: str,
    ) -> AsyncIterator[AgentEvent]:
        name = call.function.name
        try:
            arguments = json.loads(call.function.arguments)
        except json.JSONDecodeError:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}

        yield AgentEvent(
            type=AgentEventType.TOOL_START,
            data={"tool": name, "arguments": arguments},
        )
        self._log(session_id, "", "tool_start", {"tool": name, "arguments": arguments})

        result = await self._handlers.dispatch(name, arguments)

        yield AgentEvent(type=AgentEventType.TOOL_END, data={"tool": name, "result": result})
        self._log(session_id, "", "tool_end", {"tool": name, "result": result})

        messages.append(
            ChatMessage(
                role="tool",
                tool_call_id=call.id,
                content=result,
            )
        )

    def _log(self, session_id: str, user_message: str, event_type: str, payload: dict[str, Any]) -> None:
        self._session_log.append(
            SessionLogEntry(
                session_id=session_id,
                user_message=user_message,
                event_type=event_type,
                payload=payload,
            )
        )
