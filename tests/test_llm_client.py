"""Tests del cliente DeepSeek (ítem 11 — tool-use confirmado)."""

import json

import httpx
import pytest
import respx

from scraper_agent.agent.config import DeepSeekSettings
from scraper_agent.agent.llm_client import (
    DeepSeekClient,
    parse_json_plan,
    recommended_output_mode,
)
from scraper_agent.agent.llm_models import ChatMessage
from scraper_agent.agent.tools_schema import build_agent_tools, tools_as_api_payload
from scraper_agent.security_env.tool_runner import load_tool_catalog


@pytest.fixture
def settings() -> DeepSeekSettings:
    return DeepSeekSettings(api_key="test-key", base_url="https://api.deepseek.com", model="deepseek-chat")


def test_tool_use_capability_documented() -> None:
    cap = DeepSeekClient.tool_use_capability()
    assert cap["supported"] is True
    assert cap["mode"] == "tool_calls"
    assert cap["fallback_mode"] == "json_plan"
    assert "deepseek.com" in str(cap["docs_url"])


def test_recommended_output_mode_is_tool_calls() -> None:
    assert recommended_output_mode() == "tool_calls"


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_API_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    cfg = DeepSeekSettings.from_env()
    assert cfg.api_key == "sk-test"
    assert cfg.model == "deepseek-chat"


def test_settings_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        DeepSeekSettings.from_env()


def test_agent_tools_include_scraping_and_security() -> None:
    names = {t.function.name for t in build_agent_tools()}
    assert names == {
        "run_site_crawl",
        "search_crawl_output",
        "list_security_tools",
        "run_security_tool",
    }


def test_run_security_tool_enum_matches_catalog() -> None:
    tools = build_agent_tools()
    security_tool = next(t for t in tools if t.function.name == "run_security_tool")
    enum_values = security_tool.function.parameters["properties"]["tool_id"]["enum"]
    assert set(enum_values) == set(load_tool_catalog().keys())


def test_tools_as_api_payload_shape() -> None:
    payload = tools_as_api_payload()
    assert len(payload) == 4
    assert payload[0]["type"] == "function"
    assert "name" in payload[0]["function"]


@pytest.mark.asyncio
@respx.mock
async def test_chat_completion_text_response(settings: DeepSeekSettings) -> None:
    body = {
        "id": "cmpl-1",
        "model": "deepseek-chat",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hola, listo para ayudar."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    respx.post("https://api.deepseek.com/chat/completions").mock(
        return_value=httpx.Response(200, json=body)
    )
    async with DeepSeekClient(settings) as client:
        response = await client.chat_completion(
            [ChatMessage(role="user", content="Hola")],
        )
    assert response.assistant_message is not None
    assert response.assistant_message.content == "Hola, listo para ayudar."
    assert response.has_tool_calls is False


@pytest.mark.asyncio
@respx.mock
async def test_chat_completion_with_tool_calls(settings: DeepSeekSettings) -> None:
    body = {
        "id": "cmpl-2",
        "model": "deepseek-chat",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {
                                "name": "run_security_tool",
                                "arguments": json.dumps(
                                    {"tool_id": "whois", "host": "allowed.example.com"}
                                ),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    route = respx.post("https://api.deepseek.com/chat/completions").mock(
        return_value=httpx.Response(200, json=body)
    )
    async with DeepSeekClient(settings) as client:
        response = await client.chat_completion(
            [ChatMessage(role="user", content="whois de allowed.example.com")],
            tools=build_agent_tools(),
        )
    assert response.has_tool_calls is True
    call = response.assistant_message.tool_calls[0]
    assert call.function.name == "run_security_tool"
    assert route.called
    sent = json.loads(route.calls.last.request.content.decode())
    assert "tools" in sent
    assert sent["tools"][0]["function"]["name"] == "run_site_crawl"


def test_parse_json_plan_fallback() -> None:
    action = parse_json_plan(
        json.dumps({"action": "run_security_tool", "arguments": {"tool_id": "whois", "host": "x.com"}})
    )
    assert action.action == "run_security_tool"
    assert action.arguments["tool_id"] == "whois"


def test_parse_json_plan_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_json_plan("not json")


def test_from_env_optional_none_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert DeepSeekSettings.from_env_optional() is None
