"""Giudizio semantico via il provider LLM risolto (comprensibilità descrizione, 0–1).

Unico uso LLM del backend per la maturità. Fail-safe: senza provider configurato o
su errore ritorna {} → scoring deterministico. Mantiene riproducibile il pilota e i test.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..config import Settings
from ..llm import complete

log = logging.getLogger("opendata-backend.maturity.semantic")

_MAX_ITEMS = 40
_PROMPT = (
    "Per ogni dataset valuta da 0 a 1 quanto la descrizione è chiara e comprensibile "
    "per un cittadino. Rispondi SOLO con un oggetto JSON {id: punteggio}.\n\n"
)


async def semantic_clarity_map(
    items: list[dict[str, str]], *, settings: Settings
) -> dict[str, float]:
    """`items`: [{"id","title","description"}] → {id: clarity}. {} se non disponibile."""
    if not items:
        return {}
    items = items[:_MAX_ITEMS]
    text = await complete(
        settings,
        prompt=_PROMPT + json.dumps(items, ensure_ascii=False),
        max_tokens=1024,
    )
    if not text:
        return {}
    try:
        data: Any = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        log.warning("semantic clarity: risposta non JSON: %r", text[:300])
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, float] = {}
    for key, val in data.items():
        try:
            out[str(key)] = max(0.0, min(1.0, float(val)))
        except (TypeError, ValueError):
            continue
    return out
