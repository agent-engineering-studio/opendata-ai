"""Settings tests for the orchestrator."""

from __future__ import annotations

import pytest
from opendata_backend.config import (
    CKAN_INSTRUCTIONS,
    EUROSTAT_INSTRUCTIONS,
    ISPRA_INSTRUCTIONS,
    ISTAT_INSTRUCTIONS,
    OECD_INSTRUCTIONS,
    OPENCOESIONE_INSTRUCTIONS,
    OSM_INSTRUCTIONS,
    PROGRAMMA_INSTRUCTIONS,
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
    """Eurostat / OECD / OpenCoesione must be opt-in so a stack upgrade doesn't raise LLM cost."""
    for var in (
        "ENABLE_CKAN", "ENABLE_ISTAT", "ENABLE_EUROSTAT", "ENABLE_OECD", "ENABLE_OPENCOESIONE",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings()  # type: ignore[call-arg]
    assert s.enable_ckan is True
    assert s.enable_istat is True
    assert s.enable_eurostat is False
    assert s.enable_oecd is False
    assert s.enable_opencoesione is False


def test_opencoesione_settings_defaults(monkeypatch) -> None:
    for var in ("OPENCOESIONE_MCP_URL", "OPENCOESIONE_AGENT_NAME"):
        monkeypatch.delenv(var, raising=False)
    s = Settings()  # type: ignore[call-arg]
    assert s.opencoesione_mcp_url.endswith("/mcp")
    # 8082 is the eurostat host-debug convention — opencoesione must not clash.
    assert s.opencoesione_mcp_url != s.eurostat_mcp_url
    assert s.opencoesione_agent_name == "opencoesione"


def test_osm_ispra_settings_and_instructions_contract() -> None:
    """7A/7B (R5): contratto RESOURCES_JSON + flag opt-in + niente clash di porte."""
    s = Settings()  # type: ignore[call-arg]
    assert s.enable_osm is False and s.enable_ispra is False
    assert s.osm_agent_name == "osm" and s.ispra_agent_name == "ispra"
    taken = {s.ckan_mcp_url, s.istat_mcp_url, s.eurostat_mcp_url, s.oecd_mcp_url,
             s.opencoesione_mcp_url, s.osm_mcp_url}
    assert s.ispra_mcp_url not in taken

    for instructions, tool in (
        (OSM_INSTRUCTIONS, "find_nearby_places"),
        (ISPRA_INSTRUCTIONS, "ispra_risk_indicators"),
    ):
        assert "<!--RESOURCES_JSON-->" in instructions
        assert tool in instructions
    # Il synth conosce le nuove sezioni; il programma integra i vincoli ambientali.
    assert "=== OSM ===" in SYNTH_INSTRUCTIONS and "=== ISPRA ===" in SYNTH_INSTRUCTIONS
    assert "VINCOLI AMBIENTALI" in PROGRAMMA_INSTRUCTIONS
    assert "P3/P4" in PROGRAMMA_INSTRUCTIONS


def test_kg_settings_and_instructions_contract() -> None:
    """KG = memoria delle analisi (non documenti): il read recupera le analisi
    passate dal namespace `analisi-` per riuso/risparmio token (R13: niente
    tool di scrittura nel prompt)."""
    from opendata_backend.config import KG_INSTRUCTIONS

    s = Settings()  # type: ignore[call-arg]
    assert s.enable_kg is False
    assert s.kg_agent_name == "kg"
    assert s.kg_analysis_namespace_prefix == "analisi-"
    assert s.kg_ui_url is None

    assert "<!--RESOURCES_JSON-->" in KG_INSTRUCTIONS
    assert "kg_query" in KG_INSTRUCTIONS
    assert "analisi-" in KG_INSTRUCTIONS  # namespace delle analisi passate
    # I tool write non devono mai essere menzionati all'agente (R13).
    assert "kg_ingest" not in KG_INSTRUCTIONS
    assert "kg_delete_document" not in KG_INSTRUCTIONS
    assert "=== KG ===" in SYNTH_INSTRUCTIONS
    # Il programma sa che il KG è memoria di analisi passate, non dato ufficiale.
    assert "ANALISI PRECEDENTI" in PROGRAMMA_INSTRUCTIONS


def test_opencoesione_instructions_contract() -> None:
    """The R5 contract bits the parser + capture rely on must be present."""
    assert "<!--RESOURCES_JSON-->" in OPENCOESIONE_INSTRUCTIONS
    assert "source_url" in OPENCOESIONE_INSTRUCTIONS
    assert "opencoesione_funding_capacity" in OPENCOESIONE_INSTRUCTIONS
    assert "opencoesione_resolve_territorio" in OPENCOESIONE_INSTRUCTIONS
    # Citations are JSON API links, never downloadable content.
    assert '"format":"JSON"' in OPENCOESIONE_INSTRUCTIONS.replace(" ", "")
    # The synth must know the new section exists.
    assert "OPENCOESIONE" in SYNTH_INSTRUCTIONS
    assert "=== OPENCOESIONE ===" in SYNTH_INSTRUCTIONS


def test_eurostat_oecd_default_base_urls(monkeypatch) -> None:
    for var in ("EUROSTAT_SDMX_BASE_URL", "OECD_SDMX_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    s = Settings()  # type: ignore[call-arg]
    assert "ec.europa.eu/eurostat" in s.eurostat_sdmx_base_url
    assert "sdmx.oecd.org" in s.oecd_sdmx_base_url
