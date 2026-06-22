"""Spiegazione in linguaggio naturale condivisa dai use case.

Usa il provider LLM risolto. Fail-safe: senza provider configurato (o su
errore) ritorna una stringa di fallback costruita dal chiamante → use case e
test deterministici e offline.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..config import Settings
from ..llm import complete

log = logging.getLogger("opendata-backend.usecases.llm")


async def explain(
    settings: Settings, *, instructions: str, context: dict[str, Any], fallback: str
) -> str:
    """Genera una spiegazione via il provider LLM risolto, o ritorna `fallback`."""
    text = await complete(
        settings,
        prompt=f"{instructions}\n\nContesto JSON:\n{json.dumps(context, ensure_ascii=False)}",
        max_tokens=700,
    )
    return text or fallback
