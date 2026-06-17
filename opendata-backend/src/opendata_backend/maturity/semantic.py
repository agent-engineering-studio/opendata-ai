"""Giudizio semantico via Claude Haiku (comprensibilità descrizione, 0–1).

Unico uso LLM del backend per la maturità. Fail-safe: senza ANTHROPIC_API_KEY o su
errore ritorna {} → scoring deterministico. Mantiene riproducibile il pilota e i test.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("opendata-backend.maturity.semantic")

_MAX_ITEMS = 40
_PROMPT = (
    "Per ogni dataset valuta da 0 a 1 quanto la descrizione è chiara e comprensibile "
    "per un cittadino. Rispondi SOLO con un oggetto JSON {id: punteggio}.\n\n"
)


async def semantic_clarity_map(
    items: list[dict[str, str]], *, model: str
) -> dict[str, float]:
    """`items`: [{"id","title","description"}] → {id: clarity}. {} se non disponibile."""
    if not items or not os.getenv("ANTHROPIC_API_KEY"):
        return {}
    items = items[:_MAX_ITEMS]
    try:
        import anthropic

        client = anthropic.AsyncAnthropic()
        msg = await client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": _PROMPT + json.dumps(items, ensure_ascii=False)}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        data: Any = json.loads(text)
        if not isinstance(data, dict):
            return {}
        out: dict[str, float] = {}
        for key, val in data.items():
            try:
                out[str(key)] = max(0.0, min(1.0, float(val)))
            except (TypeError, ValueError):
                continue
        return out
    except Exception as exc:  # noqa: BLE001 — semantico best-effort
        log.warning("semantic clarity non disponibile: %s", exc)
        return {}
