"""Tests del agente orquestador."""

import json
from pathlib import Path

import pytest

from scraper_agent.agent.events import AgentEventType
from scraper_agent.agent.llm_client import DeepSeekClient
from scraper_agent.agent.llm_models import ChatCompletionChoice, ChatCompletionResponse, ChatMessage, ToolCall, ToolCallFunction
from scraper_agent.agent.security_scraping_agent import SecurityScrapingAgent
from scraper_agent.agent.tool_handlers import AgentDependencies, ToolHandlerRegistry
from scraper_agent.agent.config import DeepSeekSettings
from scraper_agent.security_env.tool_runner import load_tool_catalog


class MockLLM(DeepSeekClient):
    """Cliente LLM con respuestas precargadas."""

    def __init__(self, responses: list[ChatCompletionResponse]) -> None:
        super().__init__(DeepSeekSettings(api_key="test"))
        self._responses = list(responses)
        self._index = 0

    async def chat_completion(self, messages, *, tools=None, tool_choice=None, temperature=0.2, stream=False):
        if self._index >= len(self._responses):
            return ChatCompletionResponse(
                choices=[
                    ChatCompletionChoice(
                        message=ChatMessage(role="assistant", content="Fin."),
                    )
                ]
            )
        response = self._responses[self._index]
        self._index += 1
        return response

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_agent_executes_tool_then_responds(tmp_path: Path) -> None:
    async def fake_crawl(**kwargs) -> dict:
        return {"domain": "test.pe", "pages": 1, "articles": 2, "output": "out.json"}

    deps = AgentDependencies(crawl_handler=fake_crawl, session_id="sess-1")
    handlers = ToolHandlerRegistry(deps)
    session_dir = tmp_path / "sessions"

    from scraper_agent.storage.session_log import SessionLog

    tool_response = ChatCompletionResponse(
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_1",
                            function=ToolCallFunction(
                                name="run_site_crawl",
                                arguments=json.dumps({"config_path": "config/gestion_pe.yaml"}),
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ]
    )
    final_response = ChatCompletionResponse(
        choices=[
            ChatCompletionChoice(
                message=ChatMessage(
                    role="assistant",
                    content="Crawl completado: 2 artículos extraídos.",
                ),
                finish_reason="stop",
            )
        ]
    )
    llm = MockLLM([tool_response, final_response])
    agent = SecurityScrapingAgent(llm, handlers=handlers, session_log=SessionLog(session_dir), deps=deps)

    events = [event async for event in agent.run_stream("scrapea gestion.pe", session_id="sess-1")]
    types = [e.type for e in events]
    assert AgentEventType.TOOL_START in types
    assert AgentEventType.TOOL_END in types
    assert AgentEventType.FINAL in types
    final = next(e for e in events if e.type == AgentEventType.FINAL)
    assert "2" in final.data["content"]

    log_path = session_dir / "sess-1.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 3


@pytest.mark.asyncio
async def test_list_security_tools_via_handler() -> None:
    registry = ToolHandlerRegistry(AgentDependencies())
    raw = await registry.list_security_tools({})
    payload = json.loads(raw)
    assert len(payload["tools"]) == len(load_tool_catalog())
