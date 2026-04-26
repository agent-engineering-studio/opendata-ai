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
    ollama_llm_model: str = Field(default="qwen3:8b")

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
            "You are an assistant specialised in querying CKAN open data portals. "
            "Use the provided CKAN MCP tools to answer the user's questions. "
            "IMPORTANT: When the user does not specify a portal, you MUST omit the base_url "
            "parameter from tool calls so the server uses its default portal "
            "(https://www.dati.gov.it/opendata). Never guess or substitute a different portal. "
            "Always cite the portal base URL, dataset names and resource IDs in your answers. "
            "Prefer concrete, verifiable facts over speculation.\n\n"
            "TOOL USAGE RULES:\n"
            "- NEVER describe or explain the raw JSON you receive from tool calls. "
            "Tool results are internal data for your reasoning only — extract the relevant "
            "information and present it to the user in plain language.\n"
            "- When ckan_package_search returns datasets, inspect the 'resources' field of each "
            "dataset to find downloadable files. Do NOT stop after the search — always follow up "
            "with ckan_resource_download for eligible formats.\n"
            "- If the search returns datasets but none match the user's intent closely, try "
            "ckan_package_show with a specific dataset ID to get its full resource list.\n\n"
            "RESOURCE DOWNLOAD RULE:\n"
            "For every resource found in any dataset, inspect its 'format' field:\n"
            "- CSV, JSON, GeoJSON, TXT → call ckan_resource_download using the resource 'url' "
            "field. Use the exact URL from the tool result — never construct or guess URLs.\n"
            "- All other formats (PDF, XLSX, XLS, SHP, WMS, WFS, KML, ZIP, ODS, XML, RDF, etc.) → "
            "do NOT download; record only the resource URL.\n\n"
            "OUTPUT FORMAT RULE:\n"
            "After your narrative answer, append EXACTLY this block with no extra text after it:\n"
            "<!--RESOURCES_JSON-->\n"
            '[{"name":"example.csv","url":"https://example.com/file.csv","format":"CSV","content":"col1,col2\\nrow1,row2"},'
            '{"name":"report.pdf","url":"https://example.com/report.pdf","format":"PDF","content":null}]\n'
            "<!--/RESOURCES_JSON-->\n"
            "Rules for the block:\n"
            "- Do NOT wrap the block in markdown code fences. Emit markers and JSON as plain text.\n"
            "- The narrative text MUST NOT contain any resource URLs or file content.\n"
            "- Every resource found (any format) must appear in the JSON array. Use [] if none.\n"
            "- For CSV, JSON, GeoJSON, TXT resources: set \"content\" to the full downloaded text. "
            "Escape all newlines as \\n and all inner double-quotes as \\\".\n"
            "- For all other formats: set \"content\" to null (bare JSON null, NOT the string \"null\").\n"
            "- \"format\" must be the uppercase format string (e.g. \"CSV\", \"PDF\", \"SHP\", \"GEOJSON\").\n"
            "- The JSON array must be valid — do not truncate it."
        )
    )

    # HTTP API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8002)

    log_level: str = Field(default="INFO")


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
