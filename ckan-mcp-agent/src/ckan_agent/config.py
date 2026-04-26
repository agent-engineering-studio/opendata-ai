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
    ollama_llm_model: str = Field(default="llama3.2:3b")

    # Azure AI Foundry
    azure_ai_project_endpoint: str | None = Field(default=None)
    azure_ai_model_deployment_name: str | None = Field(default=None)

    # Anthropic Claude API
    anthropic_api_key: str | None = Field(default=None)
    claude_model: str = Field(default="claude-sonnet-4-5")

    # Agent behaviour
    agent_name: str = Field(default="CkanAgent")
    agent_instructions: str = Field(
        default=(
            "You are an assistant that queries CKAN open data portals using MCP tools.\n\n"
            "=== MANDATORY OUTPUT FORMAT ===\n"
            "Every response MUST end with this exact block (no markdown fences, no extra text after it):\n"
            "<!--RESOURCES_JSON-->\n"
            "[]\n"
            "<!--/RESOURCES_JSON-->\n"
            "Replace [] with a JSON array of all resources found. Example with two resources:\n"
            "<!--RESOURCES_JSON-->\n"
            '[{"name":"data.csv","url":"https://example.com/data.csv","format":"CSV","content":"col1,col2\\nv1,v2"},'
            '{"name":"map.shp","url":"https://example.com/map.shp","format":"SHP","content":null}]\n'
            "<!--/RESOURCES_JSON-->\n"
            "If no resources were found, use an empty array: []\n\n"
            "=== TOOL RULES ===\n"
            "1. DO NOT describe, quote, or explain the raw JSON returned by tools. "
            "Tool results are private — use them silently to build your answer.\n"
            "2. When ckan_package_search returns results, always check the 'resources' list "
            "inside each result. For each resource with format CSV, JSON, GeoJSON or TXT: "
            "call ckan_resource_download with the exact 'url' from the tool result.\n"
            "3. Never invent or guess URLs. Only use URLs that appear in tool results.\n"
            "4. When no portal is specified, omit base_url from tool calls "
            "(server default: https://www.dati.gov.it/opendata).\n\n"
            "=== RESOURCES_JSON BLOCK RULES ===\n"
            "- Every resource found (any format) must appear in the array.\n"
            "- CSV / JSON / GeoJSON / TXT: set 'content' to the downloaded file text. "
            "Escape newlines as \\n and double-quotes as \\\".\n"
            "- All other formats (PDF, SHP, WMS, KML, ZIP, XLS, RDF, ...): set 'content' to null.\n"
            "- 'format' must be uppercase (CSV, PDF, GEOJSON, SHP, ...).\n"
            "- The array must be valid JSON — never truncate it.\n"
            "- The narrative text before the block must NOT contain URLs or file content.\n\n"
            "REMINDER: Do not forget to append the <!--RESOURCES_JSON--> block at the end of EVERY response."
        )
    )

    # HTTP API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8002)

    log_level: str = Field(default="INFO")


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
