"""Sanity tests for Settings."""

from __future__ import annotations

from ckan_agent.config import Settings


def test_defaults_load() -> None:
    s = Settings()  # type: ignore[call-arg]
    assert s.llm_provider in {"ollama", "azure_foundry", "claude"}
    assert s.mcp_server_url.endswith("/mcp")
    assert s.ckan_default_base_url == "https://www.dati.gov.it/opendata"
    assert s.api_port > 0


def test_override_via_model_copy() -> None:
    s = Settings().model_copy(update={"llm_provider": "azure_foundry"})  # type: ignore[call-arg]
    assert s.llm_provider == "azure_foundry"
