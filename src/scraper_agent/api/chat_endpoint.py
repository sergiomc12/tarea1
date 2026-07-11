"""API HTTP del agente — endpoint único de chat."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from scraper_agent.agent.config import DeepSeekSettings
from scraper_agent.agent.events import AgentEvent
from scraper_agent.agent.llm_client import DeepSeekClient
from scraper_agent.agent.security_scraping_agent import SecurityScrapingAgent
from scraper_agent.utils.logger import setup_logging


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    chat_endpoint: str = "/chat"


def create_app(*, log_level: str = "INFO") -> FastAPI:
    load_dotenv()
    setup_logging(log_level)
    app = FastAPI(title="Scraper Agent Chat", version="0.4.0")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/chat")
    async def chat(request: ChatRequest) -> StreamingResponse:
        settings = DeepSeekSettings.from_env_optional()
        if settings is None:
            raise HTTPException(
                status_code=503,
                detail="DEEPSEEK_API_KEY no configurada",
            )
        session_id = request.session_id or str(uuid.uuid4())

        async def event_generator() -> AsyncIterator[str]:
            async with DeepSeekClient(settings) as llm:
                agent = SecurityScrapingAgent(llm)
                async for event in agent.run_stream(request.message, session_id=session_id):
                    yield _format_sse(event)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Session-Id": session_id},
        )

    return app


def _format_sse(event: AgentEvent) -> str:
    return event.to_sse()
