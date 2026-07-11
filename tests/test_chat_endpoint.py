"""Tests del endpoint POST /chat."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from scraper_agent.api.chat_endpoint import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    return TestClient(create_app(log_level="WARNING"))


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    app = create_app(log_level="WARNING")
    response = TestClient(app).post("/chat", json={"message": "hola"})
    assert response.status_code == 503


@respx.mock
def test_chat_stream_events(client: TestClient) -> None:
    llm_body = {
        "id": "cmpl-1",
        "model": "deepseek-chat",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Listo, puedo ayudarte con scraping."},
                "finish_reason": "stop",
            }
        ],
    }
    respx.post("https://api.deepseek.com/chat/completions").mock(
        return_value=httpx.Response(200, json=llm_body)
    )
    with client.stream("POST", "/chat", json={"message": "hola"}) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        chunks = list(response.iter_text())
    body = "".join(chunks)
    assert "final" in body
    assert "scraping" in body.lower()


def test_session_log_append(tmp_path) -> None:
    from scraper_agent.storage.session_log import SessionLog, SessionLogEntry

    log = SessionLog(tmp_path)
    log.append(SessionLogEntry(session_id="abc", user_message="hola", event_type="user_message"))
    entries = log.read_session("abc")
    assert len(entries) == 1
    assert entries[0]["user_message"] == "hola"
