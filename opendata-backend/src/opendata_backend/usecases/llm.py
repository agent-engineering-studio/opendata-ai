"""Spiegazione in linguaggio naturale (Sonnet) condivisa dai use case.

Fail-safe: senza ANTHROPIC_API_KEY (o su errore) ritorna una stringa di fallback
costruita dal chiamante → use case e test deterministici e offline.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("opendata-backend.usecases.llm")


async def explain(*, model: str, instructions: str, context: dict[str, Any], fallback: str) -> str:
    """Genera una spiegazione con Sonnet, o ritorna `fallback` se non disponibile."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return fallback
    try:
        import anthropic

        client = anthropic.AsyncAnthropic()
        msg = await client.messages.create(
            model=model,
            max_tokens=700,
            messages=[{
                "role": "user",
                "content": f"{instructions}\n\nContesto JSON:\n{json.dumps(context, ensure_ascii=False)}",
            }],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return text.strip() or fallback
    except Exception as exc:  # noqa: BLE001
        log.warning("explain Sonnet non disponibile: %s", exc)
        return fallback
