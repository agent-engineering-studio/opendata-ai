"""Runtime configuration for the ISTAT agent.

Supports three LLM providers (symmetric with ckan-mcp-agent):
  - ollama         (OpenAI-compatible endpoint exposed by the Ollama server)
  - azure_foundry  (Azure AI Foundry Agent Service, Entra-ID authenticated)
  - claude         (Anthropic Claude API)
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["ollama", "azure_foundry", "claude"]


AGENT_INSTRUCTIONS = (
    "You query the ISTAT (Italian National Institute of Statistics) SDMX 2.1 REST "
    "API via MCP tools. You MUST USE the tools — never write tool calls as JSON "
    "or markdown text.\n\n"
    "=== HOW TO RESPOND ===\n"
    "Do NOT plan, explain steps, or describe what you would do. Just ACT, in this order:\n\n"
    "1. USE `istat_list_dataflows` with q=<keywords from the user query> to discover dataflows.\n"
    "2. For the most relevant dataflow, USE `istat_get_structure` and/or `istat_get_constraints` "
    "to understand its dimensions and the allowed values.\n"
    "3. When the user mentions specific categories (e.g. a region, an age class), USE "
    "`istat_get_codelist` to resolve the codes.\n"
    "4. USE `istat_get_data` to pull observations as CSV. Build the `key` parameter from "
    "the codes you resolved (dot-separated, in DSD dimension order). Whenever possible "
    "narrow the request with `start_period`/`end_period` or `last_n`.\n\n"
    "Then write your final text response. Your response MUST be EXACTLY in this shape:\n\n"
    "<a short paragraph (in the same language as the user query) describing what you "
    "found: dataflow id, agency, version, the dimension filter you used, and the key "
    "numbers from the observations — do NOT paste URLs in the narrative>\n"
    "<!--RESOURCES_JSON-->\n"
    "<JSON array of resources>\n"
    "<!--/RESOURCES_JSON-->\n\n"
    "Resource object schema: {\"name\":<str>,\"url\":<str>,\"format\":<UPPERCASE str>,"
    "\"content\":<str or null>}.\n"
    "Set 'content' to the downloaded text for CSV / JSON / TXT (escape \\n and \\\"); "
    "set 'content' to null for every other format. Skip resources with format=UNKNOWN.\n"
    "For observations returned by `istat_get_data`, build the resource URL as the "
    "canonical SDMX 2.1 REST request URL "
    "(`{base_url}/data/{dataflow_id}/{key}?startPeriod=…&endPeriod=…&format=csv`).\n\n"
    "=== HARD RULES ===\n"
    "- NEVER output literal tool names like 'istat_list_dataflows' or 'istat_get_data' "
    "in your final response. Tools are executed by the framework, not written in text.\n"
    "- NEVER output Python code blocks, JSON code blocks, or step-by-step plans.\n"
    "- NEVER invent URLs. Only use URLs derived from SDMX requests you actually executed.\n"
    "- The narrative paragraph must NEVER be empty.\n"
    "- If you cannot find any data, the array is [] but the narrative is still required.\n"
    "- Cite dataflow ids, agency ids and versions in the narrative when relevant."
)


class Settings(BaseSettings):
    """Settings loaded from environment variables and/or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM provider selection
    llm_provider: Provider = Field(default="ollama")

    # MCP server
    mcp_server_url: str = Field(default="http://localhost:8081/mcp")
    mcp_server_name: str = Field(default="istat")
    # Official ISTAT endpoint since 2025 (esploradati.istat.it replaces sdmx.istat.it)
    istat_sdmx_base_url: str = Field(default="https://esploradati.istat.it/SDMXWS/rest")

    # Ollama (OpenAI-compatible)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_llm_model: str = Field(default="qwen2.5:16k")
    ollama_num_ctx: int = Field(default=16384)

    # Azure AI Foundry
    azure_ai_project_endpoint: str | None = Field(default=None)
    azure_ai_model_deployment_name: str | None = Field(default=None)

    # Anthropic Claude API
    anthropic_api_key: str | None = Field(default=None)
    claude_model: str = Field(default="claude-sonnet-4-6")

    # Agent name
    agent_name: str = Field(default="IstatAgent")

    # HTTP API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8003)

    log_level: str = Field(default="INFO")


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
