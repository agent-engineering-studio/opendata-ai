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

Provider = Literal["auto", "ollama", "azure_foundry", "claude"]


AGENT_INSTRUCTIONS = (
    "You query CKAN open data portals via MCP tools. You MUST USE the tools — "
    "never write tool calls as JSON or markdown text.\n\n"
    "=== PORTAL SELECTION ===\n"
    "If the user message starts with a 'PORTAL_HINT:' line, follow it exactly "
    "and skip the rest of this section.\n\n"
    "Otherwise, pick exactly ONE portal from this list, based on the user query "
    "(language, geographic scope, domain). If the user explicitly names a portal "
    "in the query, use that one. Otherwise infer from language and context:\n"
    "  - https://www.dati.gov.it/opendata  — Italian, Italy (default for Italian queries)\n"
    "  - https://data.gov.uk               — English, United Kingdom\n"
    "  - https://data.gov                  — English, United States\n"
    "  - https://open.canada.ca/data/en    — English, Canada\n"
    "  - https://data.gov.au               — English, Australia\n"
    "When in doubt, default to dati.gov.it. Do NOT query multiple portals.\n\n"
    "=== HOW TO RESPOND ===\n"
    "Do NOT plan, explain steps, or describe what you would do. Just ACT:\n\n"
    "First, USE the ckan_package_search tool with q=<keywords from the user query> "
    "and base_url=<the portal URL you picked above>. "
    "If you get 0 results, USE the tool one more time with shorter keywords.\n\n"
    "Then, for each result that has resources of format CSV / JSON / GeoJSON / TXT, "
    "USE the ckan_resource_download tool on each such resource URL.\n\n"
    "Finally, write your final text response. Your response MUST be EXACTLY in this shape:\n\n"
    "<a short paragraph (in the same language as the user query) describing the "
    "datasets you found and naming the portal you used, or explaining that nothing "
    "was found and what query was tried>\n"
    "<!--RESOURCES_JSON-->\n"
    "<JSON array of resources>\n"
    "<!--/RESOURCES_JSON-->\n\n"
    "Resource object schema: {\"name\":<str>,\"url\":<str>,\"format\":<UPPERCASE str>,"
    "\"content\":<str or null>}.\n"
    "Set 'content' to the downloaded file text for CSV/JSON/GeoJSON/TXT (escape \\n and \\\"); "
    "set 'content' to null for every other format. Skip resources with format=UNKNOWN.\n\n"
    "=== HARD RULES ===\n"
    "- NEVER output the literal text 'ckan_package_search' or 'ckan_resource_download' "
    "in your final response. Tools are executed by the framework, not written in text.\n"
    "- NEVER output Python code blocks, JSON code blocks, or step-by-step plans.\n"
    "- NEVER invent URLs. Only use URLs returned by tools.\n"
    "- The narrative paragraph must NEVER be empty.\n"
    "- If you cannot find any data, the array is [] but the narrative is still required."
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
    # "auto" (default) resolves at runtime: claude if ANTHROPIC_API_KEY is set,
    # else azure_foundry if the Azure AI project is configured, else ollama.
    llm_provider: Provider = Field(default="auto")

    # MCP server
    mcp_server_url: str = Field(default="http://localhost:8080/mcp")
    mcp_server_name: str = Field(default="ckan")
    ckan_default_base_url: str = Field(default="https://www.dati.gov.it/opendata")

    # Ollama (OpenAI-compatible)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_llm_model: str = Field(default="qwen2.5:16k")
    ollama_num_ctx: int = Field(default=16384)
    # temperature 0 = greedy decoding: maximises faithfulness to tool results
    # (less id/number hallucination), which matters for small local models.
    ollama_temperature: float = Field(default=0.0)

    # Azure AI Foundry
    azure_ai_project_endpoint: str | None = Field(default=None)
    azure_ai_model_deployment_name: str | None = Field(default=None)

    # Anthropic Claude API
    anthropic_api_key: str | None = Field(default=None)
    claude_model: str = Field(default="claude-sonnet-4-6")

    # Agent name
    agent_name: str = Field(default="CkanAgent")

    # HTTP API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8002)

    log_level: str = Field(default="INFO")


def resolve_provider(settings: Settings) -> Provider:
    """Resolve the effective LLM provider.

    Priority when llm_provider == "auto":
      1. claude         — if ANTHROPIC_API_KEY is set
      2. azure_foundry  — if AZURE_AI_PROJECT_ENDPOINT + deployment name are set
      3. ollama         — fallback (local inference; OLLAMA_BASE_URL may point at
                          a remote inference container in production)
    """
    if settings.llm_provider != "auto":
        return settings.llm_provider
    if settings.anthropic_api_key:
        return "claude"
    if settings.azure_ai_project_endpoint and settings.azure_ai_model_deployment_name:
        return "azure_foundry"
    return "ollama"


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
