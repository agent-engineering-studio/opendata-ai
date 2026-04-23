"""Factories that build the chat client and the agent with MCP tools wired in."""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

from agent_framework import ChatAgent, MCPStreamableHTTPTool

from .config import Settings


def build_chat_client(settings: Settings) -> Any:
    """Return a Microsoft Agent Framework chat client for the configured provider."""
    provider = settings.llm_provider

    if provider == "ollama":
        from agent_framework.openai import OpenAIChatClient

        return OpenAIChatClient(
            base_url=f"{settings.ollama_base_url.rstrip('/')}/v1",
            api_key="ollama",
            model_id=settings.ollama_llm_model,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        from agent_framework.openai import OpenAIChatClient

        return OpenAIChatClient(
            api_key=settings.openai_api_key,
            model_id=settings.openai_model,
        )

    if provider == "azure_openai":
        if not settings.azure_openai_endpoint:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT is required when LLM_PROVIDER=azure_openai")
        from agent_framework.azure import AzureOpenAIChatClient

        kwargs: dict[str, Any] = {
            "endpoint": settings.azure_openai_endpoint,
            "deployment_name": settings.azure_openai_deployment,
            "api_version": settings.azure_openai_api_version,
        }
        if settings.azure_openai_api_key:
            kwargs["api_key"] = settings.azure_openai_api_key
        else:
            from azure.identity.aio import DefaultAzureCredential

            kwargs["credential"] = DefaultAzureCredential()
        return AzureOpenAIChatClient(**kwargs)

    raise RuntimeError(f"Unsupported LLM_PROVIDER={provider!r}")


class AgentSession:
    """Async context manager that wires MCP tool + agent together.

    Usage:
        async with AgentSession(settings) as session:
            reply = await session.run("Find air quality datasets on dati.gov.it")
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stack = AsyncExitStack()
        self._agent: ChatAgent | None = None

    async def __aenter__(self) -> "AgentSession":
        mcp_tool = MCPStreamableHTTPTool(
            name=self._settings.mcp_server_name,
            url=self._settings.mcp_server_url,
            description="Tools to query any CKAN open data portal via the Action API.",
        )
        await self._stack.enter_async_context(mcp_tool)

        chat_client = build_chat_client(self._settings)
        agent = ChatAgent(
            chat_client=chat_client,
            name=self._settings.agent_name,
            instructions=self._settings.agent_instructions,
            tools=[mcp_tool],
        )
        await self._stack.enter_async_context(agent)
        self._agent = agent
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._agent = None
        await self._stack.aclose()

    async def run(self, query: str) -> str:
        if self._agent is None:
            raise RuntimeError("AgentSession not entered")
        result = await self._agent.run(query)
        text = getattr(result, "text", None)
        return text if text is not None else str(result)
