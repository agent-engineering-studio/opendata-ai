"""Classifier wrapper for the classify endpoint.

Follows the resolved system provider: on Claude it keeps a dedicated
`AsyncAnthropic` client with `cache_control: ephemeral` on the (constant)
system prompt — amortising tokens across calls inside the same 5-minute
prompt-cache window — and reports token usage. On any other provider
(Ollama local/cloud, Azure) it routes through the shared one-shot helper;
usage is unavailable there so it reports zeros.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from anthropic import AsyncAnthropic

from ..config import Settings, resolve_provider
from ..llm import complete

log = logging.getLogger("opendata-backend.classify")


_SYSTEM = (
    "You classify open-data datasets into a CALLER-PROVIDED taxonomy. "
    "Read the dataset name + description, then assign a score in [0.0, 1.0] "
    "to every category in the supplied taxonomy. A score is the probability "
    "the dataset is relevant to that category. "
    "Output STRICT JSON with one top-level key `scores`, whose value is an "
    "object mapping every taxonomy category to its score. "
    "Do NOT invent additional categories or top-level keys. "
    "Do NOT include explanations, code fences, or markdown — JSON only."
)


@dataclass
class ClassifierResponse:
    scores: dict[str, float]
    raw: str
    model: str
    usage: dict[str, int]


class Classifier:
    """Provider-aware dataset classifier.

    On Claude it owns a dedicated `AsyncAnthropic` client (prompt caching +
    usage accounting). On any other provider it delegates to `llm.complete`.
    """

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings
        self._provider = resolve_provider(settings)
        if self._provider == "claude":
            self._client: AsyncAnthropic | None = AsyncAnthropic(
                api_key=settings.anthropic_api_key
            )
            self._model = settings.claude_classify_model
        else:
            self._client = None
            self._model = _provider_model(settings, self._provider)

    async def classify(
        self,
        *,
        dataset_name: str,
        dataset_description: str | None,
        taxonomy: list[str],
    ) -> ClassifierResponse:
        user_block = (
            f"Dataset name: {dataset_name}\n"
            f"Dataset description: {dataset_description or '(none)'}\n"
            f"Taxonomy (assign a score to EACH): {json.dumps(sorted(taxonomy))}\n"
            "Return only the JSON object."
        )
        if self._client is not None:
            msg = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_block}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
            scores = _parse_scores(text, taxonomy)
            usage = {
                "input_tokens": getattr(msg.usage, "input_tokens", 0),
                "output_tokens": getattr(msg.usage, "output_tokens", 0),
                "cache_creation_input_tokens": getattr(msg.usage, "cache_creation_input_tokens", 0) or 0,
                "cache_read_input_tokens": getattr(msg.usage, "cache_read_input_tokens", 0) or 0,
            }
            return ClassifierResponse(scores=scores, raw=text, model=self._model, usage=usage)

        # Non-Claude provider: one-shot via the shared helper (no usage data).
        text = await complete(
            self._settings,
            prompt=user_block,
            system=_SYSTEM,
            max_tokens=1024,
        )
        text = text or ""
        scores = _parse_scores(text, taxonomy)
        usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        return ClassifierResponse(scores=scores, raw=text, model=self._model, usage=usage)


def _provider_model(settings: Settings, provider: str) -> str:
    """Best-effort human-readable model id for the resolved non-Claude provider."""
    if provider == "ollama":
        return settings.ollama_llm_model
    if provider == "ollama_cloud":
        return settings.ollama_cloud_model
    if provider == "azure_foundry":
        return settings.azure_ai_model_deployment_name or "azure"
    return provider


def _parse_scores(text: str, taxonomy: list[str]) -> dict[str, float]:
    """Extract `scores` JSON from the model output and clamp to the taxonomy.

    Haiku is small and may occasionally emit prose before/after the JSON; we
    grab the outermost {...} block and parse that. Any category missing from
    the response defaults to 0.0; any extra key the model invented is dropped.
    """
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        log.warning("classify response had no JSON object: %r", text[:300])
        return {c: 0.0 for c in taxonomy}
    try:
        payload: Any = json.loads(match.group())
    except json.JSONDecodeError:
        log.warning("classify response was not valid JSON: %r", match.group()[:300])
        return {c: 0.0 for c in taxonomy}
    raw_scores = payload.get("scores") if isinstance(payload, dict) else None
    if not isinstance(raw_scores, dict):
        return {c: 0.0 for c in taxonomy}
    out: dict[str, float] = {}
    for category in taxonomy:
        v = raw_scores.get(category, 0.0)
        try:
            out[category] = max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            out[category] = 0.0
    return out
