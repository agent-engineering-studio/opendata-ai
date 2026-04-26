"""Factories that build the chat client and the SequentialBuilder orchestration."""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Any

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.orchestrations import SequentialBuilder

from .config import (
    ORCHESTRATOR_INSTRUCTIONS,
    REGIONAL_SEARCH_INSTRUCTIONS,
    Settings,
)

log = logging.getLogger("ckan-agent.factory")


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


class AgentSession:
    """Async context manager that wires MCP tools + SequentialBuilder orchestration.

    Two-agent sequential pipeline:
      1. orchestrator  — searches dati.gov.it (national portal), analyses results.
                         If a regional portal is needed, it writes REGIONAL_SEARCH_CONTEXT
                         in its response. Otherwise it produces the final answer directly.
      2. regional_search — receives the full conversation context (including the
                           orchestrator output). If REGIONAL_SEARCH_CONTEXT is present,
                           it searches the identified regional portal and produces the
                           final RESOURCES_JSON response. If absent, it repeats the
                           orchestrator's answer unchanged.

    Why SequentialBuilder and not HandoffBuilder:
      HandoffBuilder injects an allow_multiple_tool_calls flag that agent_framework_ollama
      does not support (OllamaChatOptions declares it as None / not configurable).
      SequentialBuilder passes conversation context between agents without multi-tool
      injection, making it fully compatible with OllamaChatClient.

    Usage:
        async with AgentSession(settings) as session:
            reply = await session.run("Trova dati sul trasporto pubblico in Toscana")
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stack = AsyncExitStack()
        self._workflow: Any = None

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

        orchestrator = Agent(
            chat_client,
            instructions=ORCHESTRATOR_INSTRUCTIONS,
            name=self._settings.orchestrator_name,
            **agent_kwargs,
        )
        regional_agent = Agent(
            chat_client,
            instructions=REGIONAL_SEARCH_INSTRUCTIONS,
            name=self._settings.regional_agent_name,
            **agent_kwargs,
        )

        await self._stack.enter_async_context(orchestrator)
        await self._stack.enter_async_context(regional_agent)

        # chain_only_agent_responses=True: each agent receives only the previous
        # agent text messages (not raw tool calls/results), keeping the context clean.
        self._workflow = SequentialBuilder(
            participants=[orchestrator, regional_agent],
            chain_only_agent_responses=True,
        ).build()

        log.info(
            "Sequential workflow ready: %s → %s",
            self._settings.orchestrator_name,
            self._settings.regional_agent_name,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._workflow = None
        await self._stack.aclose()

    async def run(self, query: str) -> str:
        if self._workflow is None:
            raise RuntimeError("AgentSession not entered")

        result = await self._workflow.run(query)

        # WorkflowRunResult.get_outputs() returns the data payloads of "output" events.
        # In a two-agent sequential pipeline the last output is the regional agent's reply.
        outputs = result.get_outputs()
        if not outputs:
            log.warning("Sequential workflow produced no outputs for query: %r", query)
            return ""

        last = outputs[-1]
        text = getattr(last, "text", None)
        if text is not None:
            return text

        parts = [t for out in outputs if (t := getattr(out, "text", None))]
        return "\n".join(parts) if parts else str(last)
