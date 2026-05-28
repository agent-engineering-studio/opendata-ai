from __future__ import annotations

import pytest

from istat_agent.config import Settings
from istat_agent.factory import build_chat_client


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[call-arg]


def test_rejects_legacy_openai_provider() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _settings(llm_provider="openai")


def test_rejects_legacy_azure_openai_provider() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _settings(llm_provider="azure_openai")


def test_settings_allows_only_two_providers() -> None:
    s = Settings(llm_provider="ollama")
    assert s.llm_provider == "ollama"

    s = Settings(
        llm_provider="azure_foundry",
        azure_ai_project_endpoint="https://example.services.ai.azure.com/api/projects/x",
        azure_ai_model_deployment_name="gpt-5-mini",
    )
    assert s.llm_provider == "azure_foundry"

    import pydantic

    with pytest.raises(pydantic.ValidationError):
        Settings(llm_provider="azure_openai")
    with pytest.raises(pydantic.ValidationError):
        Settings(llm_provider="openai")


def test_foundry_branch_requires_endpoint() -> None:
    with pytest.raises(RuntimeError, match="AZURE_AI_PROJECT_ENDPOINT"):
        build_chat_client(_settings(llm_provider="azure_foundry"))


def test_foundry_branch_requires_deployment_name() -> None:
    with pytest.raises(RuntimeError, match="AZURE_AI_MODEL_DEPLOYMENT_NAME"):
        build_chat_client(
            _settings(
                llm_provider="azure_foundry",
                azure_ai_project_endpoint="https://x.services.ai.azure.com/api/projects/p",
            )
        )
