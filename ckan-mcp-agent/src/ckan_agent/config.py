"""Runtime configuration for the CKAN agent.

Supports three LLM providers:
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
    "You are an assistant that queries CKAN open data portals using MCP tools.\n\n"
    "Each user message starts with a PORTAL_HINT line followed by a USER QUERY line.\n"
    "  PORTAL_HINT: tells you which CKAN portal to use (or to omit base_url).\n"
    "  USER QUERY: the actual question.\n"
    "ALWAYS follow the PORTAL_HINT exactly — never decide which portal to use yourself.\n\n"
    "=== STEPS ===\n"
    "1. Call ckan_package_search with q=<keywords from USER QUERY> and the base_url "
    "from PORTAL_HINT (omit base_url if PORTAL_HINT says to omit it).\n"
    "2. If 0 results, retry once with a shorter/broader query (drop the least specific words).\n"
    "3. For each package in the results, look at its 'resources' list.\n"
    "4. For every resource whose format is CSV, JSON, GeoJSON or TXT, "
    "call ckan_resource_download with the exact 'url' from the result.\n"
    "5. Skip any resource whose format is UNKNOWN.\n\n"
    "=== TOOL RULES ===\n"
    "- Never describe or quote the raw JSON returned by tools — use it silently.\n"
    "- Never invent URLs. Only use URLs that appeared in tool results.\n"
    "- Always EXECUTE tool calls (the framework will dispatch them). "
    "Never write a JSON tool call as part of your text answer.\n\n"
    "=== OUTPUT FORMAT ===\n"
    "Your final response MUST contain:\n"
    "a) A short Italian narrative paragraph describing what was found "
    "(or, if nothing was found, what was tried and why nothing matched).\n"
    "b) Immediately after, this exact block (no markdown fences):\n"
    "<!--RESOURCES_JSON-->\n"
    "[]\n"
    "<!--/RESOURCES_JSON-->\n"
    "Replace [] with a JSON array of resources. Example:\n"
    "<!--RESOURCES_JSON-->\n"
    '[{"name":"data.csv","url":"https://example.com/data.csv","format":"CSV","content":"col1,col2\\nv1,v2"},'
    '{"name":"map.shp","url":"https://example.com/map.shp","format":"SHP","content":null}]\n'
    "<!--/RESOURCES_JSON-->\n\n"
    "=== RESOURCES_JSON RULES ===\n"
    "- Every non-UNKNOWN resource found must appear in the array.\n"
    "- CSV / JSON / GeoJSON / TXT: 'content' is the downloaded file text "
    "(escape \\n and \\\").\n"
    "- All other formats (PDF, SHP, WMS, KML, ZIP, XLS, RDF, …): 'content' is null.\n"
    "- 'format' uppercase. Array must be valid JSON.\n"
    "- Never output empty narrative text."
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
    mcp_server_url: str = Field(default="http://localhost:8080/mcp")
    mcp_server_name: str = Field(default="ckan")
    ckan_default_base_url: str = Field(default="https://www.dati.gov.it/opendata")

    # Ollama (OpenAI-compatible)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_llm_model: str = Field(default="llama3.1:16k")
    ollama_num_ctx: int = Field(default=16384)

    # Azure AI Foundry
    azure_ai_project_endpoint: str | None = Field(default=None)
    azure_ai_model_deployment_name: str | None = Field(default=None)

    # Anthropic Claude API
    anthropic_api_key: str | None = Field(default=None)
    claude_model: str = Field(default="claude-sonnet-4-5")

    # Agent name
    agent_name: str = Field(default="CkanAgent")

    # HTTP API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8002)

    log_level: str = Field(default="INFO")


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
