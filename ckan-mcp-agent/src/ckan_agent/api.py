"""FastAPI wrapper exposing the agent as a REST service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import get_settings
from .factory import AgentSession

log = logging.getLogger("ckan-agent-api")


class ChatRequest(BaseModel):
    query: str
    base_url: str | None = None  # optional override hint (agent passes it via tool args)


class ChatResponse(BaseModel):
    reply: str


_session: AgentSession | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _session
    settings = get_settings()
    log.info("Starting CKAN agent with provider=%s", settings.llm_provider)
    _session = AgentSession(settings)
    await _session.__aenter__()
    try:
        yield
    finally:
        if _session is not None:
            await _session.__aexit__(None, None, None)
            _session = None


app = FastAPI(title="CKAN Agent API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if _session is None:
        raise HTTPException(status_code=503, detail="Agent session not initialised")
    query = req.query
    if req.base_url:
        query = f"[Target portal: {req.base_url}] {query}"
    reply = await _session.run(query)
    return ChatResponse(reply=reply)


def run() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    uvicorn.run(
        "ckan_agent.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
