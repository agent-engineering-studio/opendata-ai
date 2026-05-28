"""Chat-client factory + OrchestratorSession that wires three agents.

Three agents are constructed on session entry:
  - ckan  : `Agent` with MCPStreamableHTTPTool against the CKAN MCP server
            + CKAN_INSTRUCTIONS
  - istat : `Agent` with MCPStreamableHTTPTool against the ISTAT MCP server
            + ISTAT_INSTRUCTIONS
  - synth : tool-less `Agent` with SYNTH_INSTRUCTIONS

The CKAN+ISTAT pair is wrapped in a ConcurrentBuilder workflow with the synth
agent's `.run()` used inside the aggregator callback (see workflow.py / synth.py).

`build_chat_client` is a copy of ckan_agent.factory.build_chat_client (kept in
sync by convention; duplication is intentional under the side-by-side layout).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

from agent_framework import Agent, MCPStreamableHTTPTool

from .config import (
    CKAN_INSTRUCTIONS,
    EUROSTAT_INSTRUCTIONS,
    ISTAT_INSTRUCTIONS,
    OECD_INSTRUCTIONS,
    SYNTH_INSTRUCTIONS,
    Settings,
    resolve_provider,
)
from .synth import build_aggregator
from .workflow import build_workflow

log = logging.getLogger("orchestrator.factory")


def build_chat_client(settings: Settings) -> Any:
    """Return a Microsoft Agent Framework chat client for the configured provider."""
    provider = resolve_provider(settings)
    log.info("Building chat client for provider=%s (configured=%s)", provider, settings.llm_provider)

    if provider == "ollama":
        from agent_framework_ollama import OllamaChatClient

        log.info(
            "Ollama: host=%s model=%s",
            settings.ollama_base_url, settings.ollama_llm_model,
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

        return AnthropicClient(
            api_key=settings.anthropic_api_key,
            model=settings.claude_model,
        )

    raise RuntimeError(f"Unsupported LLM_PROVIDER={provider!r}")


class OrchestratorSession:
    """Async context that holds the workflow + up to four specialist agents.

    The three SDMX-based specialists (istat / eurostat / oecd) share the same
    `istat-mcp-server` instance — its tools are SDMX 2.1 generic and only
    differ by `agency` + `base_url` per call. Each agent still gets its own
    `MCPStreamableHTTPTool` instance because the framework expects per-agent
    connection lifecycles.

    Lifecycle:
        async with OrchestratorSession(settings) as session:
            merged_text = await session.run("popolazione Toscana 2023")
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stack = AsyncExitStack()
        self._participants: list[Agent] = []
        self._aggregator: Any | None = None
        self._synth_agent: Agent | None = None
        self._enabled_sources: list[str] = []
        # agent-framework workflows reject concurrent .run() on the same instance,
        # and the participant Agents are shared — serialise requests with a lock.
        self._lock = asyncio.Lock()

    async def _enter_mcp_tool(self, name: str, url: str, description: str) -> MCPStreamableHTTPTool:
        tool = MCPStreamableHTTPTool(name=name, url=url, description=description)
        await self._stack.enter_async_context(tool)
        return tool

    async def _enter_agent(
        self,
        chat_client: Any,
        instructions: str,
        name: str,
        tools: list[Any] | None,
        default_options: dict[str, object] | None,
    ) -> Agent:
        agent = Agent(
            chat_client,
            instructions=instructions,
            name=name,
            tools=tools,
            default_options=default_options or None,
        )
        await self._stack.enter_async_context(agent)
        return agent

    async def __aenter__(self) -> "OrchestratorSession":
        s = self._settings
        enabled = [
            label for label, on in (
                ("ckan", s.enable_ckan),
                ("istat", s.enable_istat),
                ("eurostat", s.enable_eurostat),
                ("oecd", s.enable_oecd),
            )
            if on
        ]
        if not enabled:
            raise RuntimeError("At least one source must be enabled (enable_ckan / istat / eurostat / oecd)")
        self._enabled_sources = enabled
        log.info(
            "OrchestratorSession starting | provider=%s sources=%s",
            s.llm_provider, ",".join(enabled),
        )

        chat_client = build_chat_client(s)
        default_options: dict[str, object] = {}
        if resolve_provider(s) == "ollama":
            default_options["num_ctx"] = s.ollama_num_ctx
            default_options["temperature"] = s.ollama_temperature

        participants: list[Agent] = []

        if s.enable_ckan:
            ckan_mcp = await self._enter_mcp_tool(
                s.ckan_agent_name,
                s.ckan_mcp_url,
                "Tools to query any CKAN open data portal via the Action API.",
            )
            ckan_agent = await self._enter_agent(
                chat_client, CKAN_INSTRUCTIONS, s.ckan_agent_name, [ckan_mcp], default_options,
            )
            participants.append(ckan_agent)

        # Each SDMX specialist dials its OWN MCP server instance (same image,
        # different ISTAT_SDMX_BASE_URL) → the agent never passes a base_url.
        sdmx_specs: list[tuple[bool, str, str, str, str]] = [
            (s.enable_istat,    s.istat_agent_name,    ISTAT_INSTRUCTIONS,    s.istat_mcp_url,    "ISTAT SDMX tools (esploradati.istat.it)."),
            (s.enable_eurostat, s.eurostat_agent_name, EUROSTAT_INSTRUCTIONS, s.eurostat_mcp_url, "Eurostat SDMX tools (ec.europa.eu/eurostat)."),
            (s.enable_oecd,     s.oecd_agent_name,     OECD_INSTRUCTIONS,     s.oecd_mcp_url,     "OECD SDMX tools (sdmx.oecd.org)."),
        ]
        for on, name, instructions, url, desc in sdmx_specs:
            if not on:
                continue
            tool = await self._enter_mcp_tool(name, url, desc)
            agent = await self._enter_agent(
                chat_client, instructions, name, [tool], default_options,
            )
            participants.append(agent)

        if len(participants) < 1:
            raise RuntimeError("No participants enabled — refusing to start")

        synth_agent = await self._enter_agent(
            chat_client, SYNTH_INSTRUCTIONS, s.synth_agent_name, None, default_options,
        )
        self._synth_agent = synth_agent

        # Store the building blocks; a FRESH workflow is built per request in run()
        # because agent-framework workflow instances cannot be re-run concurrently
        # (and are single-shot). See run().
        self._participants = participants
        self._aggregator = build_aggregator(synth_agent)
        log.info(
            "OrchestratorSession ready (%d participants + synth)", len(participants)
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._participants = []
        self._aggregator = None
        self._synth_agent = None
        await self._stack.aclose()

    async def run(self, query: str) -> str:
        """Fan out `query` to the enabled specialists in parallel and return the synth reply.

        Builds a fresh workflow per call and serialises calls with a lock: the
        agent-framework workflow object rejects concurrent / repeat executions,
        and the participant Agents are shared across requests.
        """
        if not self._participants or self._aggregator is None:
            raise RuntimeError("OrchestratorSession not entered")
        async with self._lock:
            workflow = build_workflow(self._participants, self._aggregator)
            events = await workflow.run(query)
        outputs = events.get_outputs()
        if not outputs:
            raise RuntimeError("Orchestrator workflow produced no outputs")
        # Aggregator returns a single AgentResponse-like; extract its text.
        final = outputs[0]
        text = getattr(final, "text", None)
        if text is None:
            messages = getattr(final, "messages", None)
            if messages:
                text = getattr(messages[-1], "text", None)
        return text if text is not None else str(final)
