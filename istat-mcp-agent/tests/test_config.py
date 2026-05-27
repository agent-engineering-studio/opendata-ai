"""Unit tests for the agent configuration layer."""

from __future__ import annotations

from istat_agent.config import Settings


def test_defaults_pick_auto_provider(monkeypatch) -> None:
    for var in ("LLM_PROVIDER", "AZURE_AI_PROJECT_ENDPOINT", "AZURE_AI_MODEL_DEPLOYMENT_NAME", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    s = Settings()  # type: ignore[call-arg]
    assert s.llm_provider == "auto"
    assert s.mcp_server_name == "istat"
    assert s.istat_sdmx_base_url.startswith("https://esploradati.istat.it")


def test_auto_resolves_to_ollama_without_creds(monkeypatch) -> None:
    from istat_agent.config import resolve_provider

    for var in ("ANTHROPIC_API_KEY", "AZURE_AI_PROJECT_ENDPOINT", "AZURE_AI_MODEL_DEPLOYMENT_NAME"):
        monkeypatch.delenv(var, raising=False)
    assert resolve_provider(Settings(llm_provider="auto")) == "ollama"  # type: ignore[call-arg]
    assert resolve_provider(
        Settings(llm_provider="auto", anthropic_api_key="sk-x")  # type: ignore[call-arg]
    ) == "claude"


def test_override_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "azure_foundry")
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/api/projects/x")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o")
    s = Settings()  # type: ignore[call-arg]
    assert s.llm_provider == "azure_foundry"
    assert s.azure_ai_project_endpoint == "https://example.services.ai.azure.com/api/projects/x"
    assert s.azure_ai_model_deployment_name == "gpt-4o"
