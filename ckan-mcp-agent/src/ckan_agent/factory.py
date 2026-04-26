"""Factories that build the chat client and the SequentialBuilder orchestration."""

from __future__ import annotations

import logging
import re
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

_REGIONAL_CTX_RE = re.compile(r"REGIONAL_SEARCH_CONTEXT\s*:", re.IGNORECASE)


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

        self._orchestrator = orchestrator
        self._regional_agent = regional_agent

        log.info(
            "Agents ready: %s → %s",
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

        # A SequentialBuilder Workflow is stateful and does not support concurrent
        # executions. Build a fresh workflow per request so concurrent HTTP requests
        # each get their own independent execution context.
        workflow = SequentialBuilder(
            participants=[self._orchestrator, self._regional_agent],
            chain_only_agent_responses=True,
        ).build()

        result = await workflow.run(query)
        outputs = result.get_outputs()
        if not outputs:
            log.warning("Sequential workflow produced no outputs for query: %r", query)
            return ""

        last_output = outputs[-1]
        if not isinstance(last_output, list):
            text = getattr(last_output, "text", None)
            return text if text is not None else str(last_output)

        # SequentialBuilder produces list[Message] containing the full conversation.
        # We need to pick the right agent's message:
        # - If the orchestrator emitted REGIONAL_SEARCH_CONTEXT, the regional_search
        #   ran a portal search → return the regional_search's last assistant message
        # - Otherwise the orchestrator's answer is the final one → return it
        assistant_messages = [
            msg for msg in last_output
            if (role := getattr(msg, "role", None))
            and getattr(role, "value", role) == "assistant"
            and getattr(msg, "text", None)
        ]
        if not assistant_messages:
            log.warning("No assistant messages in workflow output")
            return ""

        orchestrator_msg = assistant_messages[0]
        orchestrator_text = orchestrator_msg.text

        if _REGIONAL_CTX_RE.search(orchestrator_text):
            # Regional handoff path: the answer is the regional_search's reply
            # (the LAST assistant message). Fall back to orchestrator if absent.
            if len(assistant_messages) >= 2:
                log.info("Regional handoff: returning regional_search output")
                return assistant_messages[-1].text
            log.warning(
                "Orchestrator emitted REGIONAL_SEARCH_CONTEXT but no regional reply found"
            )
            return orchestrator_text

        # No handoff: orchestrator already produced the final answer
        log.info("No handoff: returning orchestrator output")
        return orchestrator_text
