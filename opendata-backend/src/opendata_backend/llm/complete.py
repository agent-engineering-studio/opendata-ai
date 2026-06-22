"""One-shot LLM completion routed through the resolved system provider.

The auxiliary LLM paths (territory/value narratives, semantic-maturità,
classify) used to hardcode `anthropic.AsyncAnthropic()`, so they always hit
Claude even when the synth agent ran on Ollama. This helper routes them
through `resolve_provider()` + `build_chat_client()` instead, so they follow
the same provider as everything else: Ollama (local/cloud), Claude or Azure.

Fail-safe by design: `complete()` returns `None` on any error or when the
resolved provider has no usable credential, and every caller keeps its own
deterministic offline fallback.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import Settings, resolve_provider

log = logging.getLogger("opendata-backend.llm")


def llm_configured(settings: Settings) -> bool:
    """True when the resolved provider has the credentials it needs.

    Lets callers skip the call (and stay offline in tests) without building a
    client. `ollama` (local) is always "configured" — reachability is decided
    at call time and handled fail-safe.
    """
    provider = resolve_provider(settings)
    if provider == "claude":
        return bool(settings.anthropic_api_key)
    if provider == "ollama_cloud":
        return bool(settings.ollama_cloud_api_key)
    if provider == "azure_foundry":
        return bool(
            settings.azure_ai_project_endpoint
            and settings.azure_ai_model_deployment_name
        )
    return True  # ollama (local)


async def complete(
    settings: Settings,
    *,
    prompt: str,
    system: str | None = None,
    max_tokens: int = 700,
    temperature: float = 0.0,
) -> str | None:
    """Run a single user turn through the system provider; `None` on failure.

    The model is the one baked into the resolved provider by
    `build_chat_client` (claude_model / ollama_llm_model / …), so callers no
    longer pass a hardcoded Claude model name.
    """
    if not llm_configured(settings):
        return None
    provider = resolve_provider(settings)
    try:
        from agent_framework import Message

        from ..factory import build_chat_client

        client = build_chat_client(settings)
        messages = []
        if system:
            messages.append(Message(role="system", contents=[system]))
        messages.append(Message(role="user", contents=[prompt]))
        options: dict[str, Any] = {
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = await client.get_response(messages, options=options)
        text = (resp.text or "").strip()
        return text or None
    except Exception as exc:  # noqa: BLE001 — best-effort, callers fall back
        log.warning("llm.complete failed (provider=%s): %s", provider, exc)
        return None
