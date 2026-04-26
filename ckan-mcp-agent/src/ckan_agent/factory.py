"""Factories that build the chat client and the two-agent orchestration pipeline."""

from __future__ import annotations

import logging
import re
from contextlib import AsyncExitStack
from typing import Any

from agent_framework import Agent, MCPStreamableHTTPTool

from .config import (
    ORCHESTRATOR_INSTRUCTIONS,
    REGIONAL_SEARCH_INSTRUCTIONS,
    Settings,
)

log = logging.getLogger("ckan-agent.factory")

# Marker the orchestrator writes when it decides a regional search is needed.
_REGIONAL_CTX_RE = re.compile(r"REGIONAL_SEARCH_CONTEXT:", re.IGNORECASE)


def build_chat_client(settings: Settings) -> Any:
    """Return a Microsoft Agent Framework chat client for the configured provider."""
    provider = settings.llm_provider
    log.info("Building chat client for provider=%s", provider)

    if provider == "ollama":
        from agent_framework_ollama import OllamaChatClient

        log.info(
            "Ollama: host=%s model=%s num_ctx=%d",
            settings.ollama_base_url, settings.ollama_llm_model, settings.ollama_num_ctx,
        )
        return OllamaChatClient(
            host=settings.ollama_base_url,
            model=settings.ollama_llm_model,
        )

    if provider == "azure_foundry":
        if not settings.azure_ai_project_endpoint:
            raise RuntimeError(
                "AZURE_AI_PROJECT_ENDPOINT is required when LLM_PROVIDER=azure_foundry"
            )
        if not settings.azure_ai_model_deployment_name:
            raise RuntimeError(
                "AZURE_AI_MODEL_DEPLOYMENT_NAME is required when LLM_PROVIDER=azure_foundry"
            )
        from agent_framework_foundry import FoundryChatClient
        from azure.identity.aio import DefaultAzureCredential

        log.info(
            "Foundry: endpoint=%s model=%s",
            settings.azure_ai_project_endpoint,
            settings.azure_ai_model_deployment_name,
        )
        return FoundryChatClient(
            project_endpoint=settings.azure_ai_project_endpoint,
            model=settings.azure_ai_model_deployment_name,
            credential=DefaultAzureCredential(),
        )

    if provider == "claude":
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=claude"
            )
        from agent_framework_anthropic import AnthropicClient

        log.info("Claude: model=%s", settings.claude_model)
        return AnthropicClient(
            api_key=settings.anthropic_api_key,
            model=settings.claude_model,
        )

    raise RuntimeError(f"Unsupported LLM_PROVIDER={provider!r}")


def _agent_text(result: Any) -> str:
    text = getattr(result, "text", None)
    return text if text is not None else str(result)


class AgentSession:
    """Async context manager that wires MCP tools + sequential two-agent orchestration.

    Two-agent pipeline (Python-level orchestration):
      1. orchestrator  — searches dati.gov.it, decides if a regional search is needed.
                         If yes, outputs a REGIONAL_SEARCH_CONTEXT block.
      2. regional_search — activated only when orchestrator emits REGIONAL_SEARCH_CONTEXT.
                           Searches the identified regional portal and produces the final answer.

    Note: HandoffBuilder from agent-framework-orchestrations is not used here because
    OllamaChatClient does not support the `allow_multiple_tool_calls` parameter that
    HandoffBuilder injects. The same two-agent logic is implemented at the Python level.

    Usage:
        async with AgentSession(settings) as session:
            reply = await session.run("Trova dati sul trasporto pubblico in Toscana")
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stack = AsyncExitStack()
        self._orchestrator: Agent | None = None
        self._regional_agent: Agent | None = None

    async def __aenter__(self) -> "AgentSession":
        log.info("Connecting to MCP server at %s", self._settings.mcp_server_url)

        mcp_tool = MCPStreamableHTTPTool(
            name=self._settings.mcp_server_name,
            url=self._settings.mcp_server_url,
            description="Tools to query any CKAN open data portal via the Action API.",
        )
        await self._stack.enter_async_context(mcp_tool)

        chat_client = build_chat_client(self._settings)
        default_options: dict[str, object] = {}
        if self._settings.llm_provider == "ollama":
            default_options["num_ctx"] = self._settings.ollama_num_ctx

        agent_kwargs: dict[str, Any] = dict(
            tools=[mcp_tool],
            default_options=default_options or None,
        )

        self._orchestrator = Agent(
            chat_client,
            instructions=ORCHESTRATOR_INSTRUCTIONS,
            name=self._settings.orchestrator_name,
            **agent_kwargs,
        )
        self._regional_agent = Agent(
            chat_client,
            instructions=REGIONAL_SEARCH_INSTRUCTIONS,
            name=self._settings.regional_agent_name,
            **agent_kwargs,
        )

        await self._stack.enter_async_context(self._orchestrator)
        await self._stack.enter_async_context(self._regional_agent)

        log.info(
            "Two-agent pipeline ready: %s → (if needed) %s",
            self._settings.orchestrator_name,
            self._settings.regional_agent_name,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._orchestrator = None
        self._regional_agent = None
        await self._stack.aclose()

    async def run(self, query: str) -> str:
        if self._orchestrator is None or self._regional_agent is None:
            raise RuntimeError("AgentSession not entered")

        # Phase 1 — orchestrator searches the national portal.
        log.info("[%s] Running on query: %r", self._settings.orchestrator_name, query)
        orch_result = await self._orchestrator.run(query)
        orch_text = _agent_text(orch_result)
        log.debug("[%s] Output length: %d chars", self._settings.orchestrator_name, len(orch_text))

        # Phase 2 — if the orchestrator identified a regional portal, delegate.
        if _REGIONAL_CTX_RE.search(orch_text):
            log.info(
                "[%s] REGIONAL_SEARCH_CONTEXT detected — activating %s",
                self._settings.orchestrator_name,
                self._settings.regional_agent_name,
            )
            regional_query = (
                f"The orchestrator has searched the national portal and found the following context.\n"
                f"Complete the regional search as instructed.\n\n"
                f"{orch_text}"
            )
            regional_result = await self._regional_agent.run(regional_query)
            return _agent_text(regional_result)

        # No regional search needed — return orchestrator's answer directly.
        log.info("[%s] No regional handoff needed — returning directly", self._settings.orchestrator_name)
        return orch_text
