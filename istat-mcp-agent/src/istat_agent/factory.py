"""Factories that build the chat client and the agent with MCP tools wired in.

Three LLM providers are supported (symmetric with ckan-mcp-agent):
  - ollama         (OpenAI-compatible endpoint served by the Ollama daemon)
  - azure_foundry  (Azure AI Foundry Agent Service, Entra-ID authenticated)
  - claude         (Anthropic Claude API)
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Any

from agent_framework import Agent, MCPStreamableHTTPTool

from .config import AGENT_INSTRUCTIONS, Settings, resolve_provider

log = logging.getLogger("istat-agent.factory")


def build_chat_client(settings: Settings) -> Any:
    """Return a Microsoft Agent Framework chat client for the configured provider."""
    provider = resolve_provider(settings)
    log.info("Building chat client for provider=%s (configured=%s)", provider, settings.llm_provider)

    if provider == "ollama":
        from agent_framework_ollama import OllamaChatClient

        log.info("Ollama: host=%s model=%s", settings.ollama_base_url, settings.ollama_llm_model)
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
    """Async context manager that wires the ISTAT MCP tool + agent together."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stack = AsyncExitStack()
        self._agent: Agent | None = None

    async def __aenter__(self) -> "AgentSession":
        log.info("Connecting to MCP server at %s", self._settings.mcp_server_url)
        mcp_tool = MCPStreamableHTTPTool(
            name=self._settings.mcp_server_name,
            url=self._settings.mcp_server_url,
            description=(
                "Tools to query the ISTAT SDMX REST API: dataflows, structures, "
                "codelists, concepts, available constraints, and observations (CSV)."
            ),
        )
        try:
            await self._stack.enter_async_context(mcp_tool)
            tool_names = [t.name for t in getattr(mcp_tool, "_tools", None) or getattr(mcp_tool, "tools", None) or []]
            log.info("MCP tool connected; discovered tools: %s", tool_names or "(list not exposed on this SDK version)")
        except Exception:
            log.exception("Failed to connect to MCP server at %s", self._settings.mcp_server_url)
            raise

        chat_client = build_chat_client(self._settings)
        default_options: dict[str, object] = {}
        if resolve_provider(self._settings) == "ollama":
            default_options["num_ctx"] = self._settings.ollama_num_ctx
            default_options["temperature"] = self._settings.ollama_temperature

        agent = Agent(
            chat_client,
            instructions=AGENT_INSTRUCTIONS,
            name=self._settings.agent_name,
            tools=[mcp_tool],
            default_options=default_options or None,
        )
        try:
            await self._stack.enter_async_context(agent)
            log.info("Agent '%s' ready", self._settings.agent_name)
        except Exception:
            log.exception("Failed to initialise Agent")
            raise
        self._agent = agent
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._agent = None
        await self._stack.aclose()

    async def run(self, query: str) -> str:
        if self._agent is None:
            raise RuntimeError("AgentSession not entered")
        log.debug("agent.run query=%r", query[:200])
        result = await self._agent.run(query)
        log.debug("agent.run raw result type=%s repr=%r", type(result).__name__, str(result)[:300])
        text = getattr(result, "text", None)
        return text if text is not None else str(result)
