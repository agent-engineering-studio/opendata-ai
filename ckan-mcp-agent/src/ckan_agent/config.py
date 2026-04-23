"""Runtime configuration for the CKAN agent.

Supports two LLM providers:
  - ollama         (OpenAI-compatible endpoint exposed by the Ollama server)
  - azure_openai   (Azure OpenAI Service deployment)
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["ollama", "azure_openai", "openai"]


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
    ollama_llm_model: str = Field(default="qwen2.5:14b")

    # Azure OpenAI
    azure_openai_endpoint: str | None = Field(default=None)
    azure_openai_api_key: str | None = Field(default=None)
    azure_openai_deployment: str = Field(default="gpt-4o-mini")
    azure_openai_api_version: str = Field(default="2024-10-21")

    # Vanilla OpenAI (fallback)
    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")

    # Agent behaviour
    agent_name: str = Field(default="CkanAgent")
    agent_instructions: str = Field(
        default=(
            "You are an assistant specialised in querying CKAN open data portals. "
            "Use the provided CKAN MCP tools to answer the user's questions. "
            "When the user does not specify a portal, assume the default one. "
            "Always cite the portal base URL, dataset names and resource IDs in your answers. "
            "Prefer concrete, verifiable facts over speculation."
        )
    )

    # HTTP API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8002)

    log_level: str = Field(default="INFO")


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
