"""Factories that build the chat client and the agent pipeline.

Architecture: deterministic Python router + single CKAN search agent.

  Why not LLM-based orchestration:
    Smaller open models (llama3.1:8b) are unreliable at following multi-mode
    instructions like "if region detected emit MARKER else produce final answer".
    They tend to either hallucinate text-formatted tool calls or pick the wrong
    branch. We move the routing decision to deterministic Python regex matching
    against a known list of Italian regional portals, and give the agent a single
    unambiguous job: search the portal pre-selected by the router.

  Flow:
    1. detect_region(query) → (region, portal_url) or (None, None) via regex
    2. Python rewrites the user query, prefixing an explicit portal hint
    3. Single agent runs ckan_package_search → ckan_resource_download
       and produces narrative + RESOURCES_JSON
"""

from __future__ import annotations

import logging
import re
from contextlib import AsyncExitStack
from typing import Any

from agent_framework import Agent, MCPStreamableHTTPTool

from .config import AGENT_INSTRUCTIONS, Settings, resolve_provider

log = logging.getLogger("ckan-agent.factory")


# Italian regional CKAN portals known to host open data harvested separately
# from the national portal (dati.gov.it). Order matters only for logging — the
# regex below is alternation-based and the first match wins.
_REGIONAL_PORTALS: list[tuple[str, str, str]] = [
    # (canonical_name, regex_alternation, portal_url)
    ("Toscana",        r"toscan[ao]|tuscany",                       "https://dati.toscana.it"),
    ("Lombardia",      r"lombard[io]a?",                            "https://www.dati.lombardia.it"),
    ("Piemonte",       r"piemont[ei]|piedmont",                     "https://www.dati.piemonte.it/catalogodati/catalog"),
    ("Emilia-Romagna", r"emilia[\s-]*romagna",                      "https://dati.emiliaromagna.it"),
    ("Lazio",          r"lazi[oa]",                                 "https://dati.lazio.it/catalog"),
    ("Veneto",         r"venet[oa]",                                "https://dati.veneto.it"),
    ("Campania",       r"campan[io]a?",                             "https://dati.regione.campania.it"),
    ("Sicilia",        r"sicil[io]a?n?",                            "https://dati.regione.sicilia.it"),
]

# Compile once at module load.
_REGION_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (name, re.compile(rf"\b({pattern})\b", re.IGNORECASE), url)
    for name, pattern, url in _REGIONAL_PORTALS
]


def detect_region(query: str) -> tuple[str | None, str | None]:
    """Return (region_name, portal_url) if the query mentions an Italian region, else (None, None)."""
    for name, pattern, url in _REGION_PATTERNS:
        if pattern.search(query):
            return name, url
    return None, None


def build_chat_client(settings: Settings) -> Any:
    """Return a Microsoft Agent Framework chat client for the configured provider."""
    provider = resolve_provider(settings)
    log.info("Building chat client for provider=%s (configured=%s)", provider, settings.llm_provider)

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
    """Single-agent CKAN session with deterministic Python region routing.

    Usage:
        async with AgentSession(settings) as session:
            reply = await session.run("Trova dati sul trasporto pubblico in Toscana")
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stack = AsyncExitStack()
        self._agent: Agent | None = None

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
        await self._stack.enter_async_context(agent)
        self._agent = agent
        log.info("Agent '%s' ready", self._settings.agent_name)
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._agent = None
        await self._stack.aclose()

    async def run(self, query: str) -> str:
        if self._agent is None:
            raise RuntimeError("AgentSession not entered")

        region, portal = detect_region(query)
        if region:
            log.info("Region detected: %s → %s", region, portal)
            enriched = (
                f"PORTAL_HINT: use base_url={portal} for all CKAN tool calls (region: {region}).\n"
                f"USER QUERY: {query}"
            )
        else:
            log.info("No region detected — agent will pick a portal from the international list")
            enriched = query

        result = await self._agent.run(enriched)
        text = getattr(result, "text", None)
        return text if text is not None else str(result)
