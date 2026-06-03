"""Settings tests for the orchestrator."""

from __future__ import annotations

import pytest
from opendata_backend.config import (
    CKAN_INSTRUCTIONS,
    EUROSTAT_INSTRUCTIONS,
    ISTAT_INSTRUCTIONS,
    OECD_INSTRUCTIONS,
    SYNTH_INSTRUCTIONS,
    Settings,
)


def test_defaults(monkeypatch) -> None:
    for var in (
        "LLM_PROVIDER",
        "CKAN_MCP_URL",
        "ISTAT_MCP_URL",
        "AZURE_AI_PROJECT_ENDPOINT",
        "AZURE_AI_MODEL_DEPLOYMENT_NAME",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings()  # type: ignore[call-arg]
    assert s.llm_provider == "auto"
    assert s.ckan_mcp_url.endswith("/mcp")
    assert s.istat_mcp_url.endswith("/mcp")
    assert s.api_port == 8000
    assert s.ollama_temperature == 0.0


def test_resolve_provider_priority(monkeypatch) -> None:
    from opendata_backend.config import resolve_provider

    for var in ("ANTHROPIC_API_KEY", "AZURE_AI_PROJECT_ENDPOINT", "AZURE_AI_MODEL_DEPLOYMENT_NAME"):
        monkeypatch.delenv(var, raising=False)

    # auto + no creds → ollama
    assert resolve_provider(Settings(llm_provider="auto")) == "ollama"  # type: ignore[call-arg]
    # auto + anthropic key → claude (highest priority)
    assert resolve_provider(
        Settings(llm_provider="auto", anthropic_api_key="sk-x")  # type: ignore[call-arg]
    ) == "claude"
    # auto + azure (no claude) → azure_foundry
    assert resolve_provider(
        Settings(  # type: ignore[call-arg]
            llm_provider="auto",
            azure_ai_project_endpoint="https://h.services.ai.azure.com/api/projects/p",
            azure_ai_model_deployment_name="gpt-5",
        )
    ) == "azure_foundry"
    # claude key beats azure when both present
    assert resolve_provider(
        Settings(  # type: ignore[call-arg]
            llm_provider="auto",
            anthropic_api_key="sk-x",
            azure_ai_project_endpoint="https://h.services.ai.azure.com/api/projects/p",
            azure_ai_model_deployment_name="gpt-5",
        )
    ) == "claude"
    # explicit provider is honoured verbatim
    assert resolve_provider(Settings(llm_provider="ollama", anthropic_api_key="sk-x")) == "ollama"  # type: ignore[call-arg]


def test_overrides(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("CKAN_MCP_URL", "http://ckan-mcp:9999/mcp")
    monkeypatch.setenv("ISTAT_MCP_URL", "http://istat-mcp:9999/mcp")
    s = Settings()  # type: ignore[call-arg]
    assert s.llm_provider == "claude"
    assert s.anthropic_api_key == "sk-test"
    assert s.ckan_mcp_url == "http://ckan-mcp:9999/mcp"
    assert s.istat_mcp_url == "http://istat-mcp:9999/mcp"


def test_rejects_unknown_provider() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        Settings(llm_provider="bogus")  # type: ignore[call-arg]


def test_instructions_constants_are_non_empty() -> None:
    """Catches regressions where the verbatim copies get accidentally cleared."""
    assert "PORTAL SELECTION" in CKAN_INSTRUCTIONS or "PORTAL_HINT" in CKAN_INSTRUCTIONS
    assert "ISTAT" in ISTAT_INSTRUCTIONS and "SDMX" in ISTAT_INSTRUCTIONS
    assert "synthesiser" in SYNTH_INSTRUCTIONS.lower()


def test_sdmx_specialists_share_template_but_differ_on_endpoint() -> None:
    """ISTAT / Eurostat / OECD instructions must each bake in their own agency + base_url."""
    assert "IT1" in ISTAT_INSTRUCTIONS
    assert "esploradati.istat.it" in ISTAT_INSTRUCTIONS

    assert "ESTAT" in EUROSTAT_INSTRUCTIONS
    assert "ec.europa.eu/eurostat" in EUROSTAT_INSTRUCTIONS

    assert "OECD" in OECD_INSTRUCTIONS
    assert "sdmx.oecd.org" in OECD_INSTRUCTIONS

    # Make sure we didn't accidentally leak ISTAT base_url into the others.
    assert "esploradati.istat.it" not in EUROSTAT_INSTRUCTIONS
    assert "esploradati.istat.it" not in OECD_INSTRUCTIONS


def test_enable_flags_default_to_ckan_istat_only(monkeypatch) -> None:
    """Eurostat / OECD must be opt-in so a stack upgrade doesn't triple LLM cost."""
    for var in ("ENABLE_CKAN", "ENABLE_ISTAT", "ENABLE_EUROSTAT", "ENABLE_OECD"):
        monkeypatch.delenv(var, raising=False)
    s = Settings()  # type: ignore[call-arg]
    assert s.enable_ckan is True
    assert s.enable_istat is True
    assert s.enable_eurostat is False
    assert s.enable_oecd is False


def test_eurostat_oecd_default_base_urls(monkeypatch) -> None:
    for var in ("EUROSTAT_SDMX_BASE_URL", "OECD_SDMX_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    s = Settings()  # type: ignore[call-arg]
    assert "ec.europa.eu/eurostat" in s.eurostat_sdmx_base_url
    assert "sdmx.oecd.org" in s.oecd_sdmx_base_url
