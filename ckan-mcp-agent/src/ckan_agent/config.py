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

_RESOURCES_JSON_FORMAT = (
    "=== MANDATORY OUTPUT FORMAT ===\n"
    "Every response MUST have:\n"
    "a) A non-empty narrative paragraph in Italian describing what was found "
    "(or explaining why nothing was found and what was tried).\n"
    "b) Immediately after the narrative, this exact block (no markdown fences):\n"
    "<!--RESOURCES_JSON-->\n"
    "[]\n"
    "<!--/RESOURCES_JSON-->\n"
    "Replace [] with a JSON array of all resources found. Example:\n"
    "<!--RESOURCES_JSON-->\n"
    '[{"name":"data.csv","url":"https://example.com/data.csv","format":"CSV","content":"col1,col2\\nv1,v2"},'
    '{"name":"map.shp","url":"https://example.com/map.shp","format":"SHP","content":null}]\n'
    "<!--/RESOURCES_JSON-->\n\n"
    "=== RESOURCES_JSON RULES ===\n"
    "- Every resource found (any format, except format=UNKNOWN) must appear in the array.\n"
    "- CSV / JSON / GeoJSON / TXT: set 'content' to the downloaded file text. "
    "Escape newlines as \\n and double-quotes as \\\".\n"
    "- All other formats (PDF, SHP, WMS, KML, ZIP, XLS, RDF, WMS, ...): set 'content' to null.\n"
    "- 'format' must be uppercase (CSV, PDF, GEOJSON, SHP, ...).\n"
    "- Never truncate the JSON array.\n"
    "- Never output an empty text. Always write at least one sentence before the block."
)

_TOOL_RULES = (
    "=== TOOL RULES ===\n"
    "1. Never describe or quote raw JSON from tools — use results silently to build your answer.\n"
    "2. When ckan_package_search returns results, check 'resources' inside each result. "
    "For each resource with format CSV, JSON, GeoJSON or TXT: "
    "call ckan_resource_download with the exact 'url' from the tool result.\n"
    "3. Never invent or guess URLs. Only use URLs from tool results.\n"
    "4. If a search returns 0 results, try a simpler or broader query before giving up.\n"
)

ORCHESTRATOR_INSTRUCTIONS = (
    "You are the Orchestrator in a two-agent CKAN data discovery pipeline.\n\n"
    "=== STEP 1: Detect region in the user query ===\n"
    "Check if the query explicitly mentions one of these Italian regions:\n"
    "  Toscana → https://dati.toscana.it\n"
    "  Lombardia → https://www.dati.lombardia.it\n"
    "  Piemonte → https://www.dati.piemonte.it/catalogodati/catalog\n"
    "  Emilia-Romagna → https://dati.emiliaromagna.it\n"
    "  Lazio → https://dati.lazio.it/catalog\n"
    "  Veneto → https://dati.veneto.it\n"
    "  Campania → https://dati.regione.campania.it\n"
    "  Sicilia → https://dati.regione.sicilia.it\n\n"
    "=== STEP 2: Decide which mode to run ===\n\n"
    "MODE A — REGIONAL DELEGATION (region detected in query):\n"
    "  Output ONLY the following block, with NO narrative, NO greeting, NO additional text.\n"
    "  No RESOURCES_JSON in this mode.\n\n"
    "  REGIONAL_SEARCH_CONTEXT:\n"
    "  - region: <region name>\n"
    "  - portal: <regional portal URL from the table above>\n"
    "  - query: <a short Italian search phrase, max 5 words, distilled from the user query>\n"
    "  - national_resources: NONE\n\n"
    "MODE B — NATIONAL ANSWER (no region detected):\n"
    "  Search dati.gov.it (omit base_url — server default applies).\n"
    "  For each resource of format CSV/JSON/GeoJSON/TXT call ckan_resource_download.\n"
    "  Output: a short Italian narrative paragraph + the RESOURCES_JSON block.\n\n"
    "CRITICAL: NEVER mix the two modes. If you output REGIONAL_SEARCH_CONTEXT, do NOT add narrative or RESOURCES_JSON.\n\n"
    + _TOOL_RULES + "\n"
    + _RESOURCES_JSON_FORMAT
)

REGIONAL_SEARCH_INSTRUCTIONS = (
    "You are the Regional Search specialist.\n\n"
    "The previous message contains either:\n"
    "  (a) a REGIONAL_SEARCH_CONTEXT block with `portal` and `query` fields, or\n"
    "  (b) a final answer that already includes a RESOURCES_JSON block.\n\n"
    "=== IF THE PREVIOUS MESSAGE CONTAINS 'REGIONAL_SEARCH_CONTEXT:' ===\n"
    "1. Extract the portal URL and query string from the block.\n"
    "2. Call ckan_package_search with base_url=<portal> and q=<query>.\n"
    "3. If 0 results, retry with a single broader keyword from the query.\n"
    "4. For every resource of format CSV/JSON/GeoJSON/TXT in the results, "
    "call ckan_resource_download with the exact url.\n"
    "5. Output an Italian narrative paragraph describing what was found, then "
    "the RESOURCES_JSON block listing every non-UNKNOWN resource.\n\n"
    "=== IF THE PREVIOUS MESSAGE ALREADY CONTAINS '<!--RESOURCES_JSON-->' ===\n"
    "Do NOT call any tools. Repeat the previous message verbatim — copy every "
    "character, especially the RESOURCES_JSON block.\n\n"
    + _TOOL_RULES + "\n"
    + _RESOURCES_JSON_FORMAT
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

    # Agent names (overridable for multi-tenant deployments)
    orchestrator_name: str = Field(default="orchestrator")
    regional_agent_name: str = Field(default="regional_search")

    # HTTP API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8002)

    log_level: str = Field(default="INFO")


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
