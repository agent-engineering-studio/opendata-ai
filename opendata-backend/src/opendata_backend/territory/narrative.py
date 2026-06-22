"""Narrazione del report territoriale via il provider LLM risolto (fail-safe offline)."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..config import Settings
from ..llm import complete

log = logging.getLogger("opendata-backend.territory.narrative")

_PROMPT = (
    "Sei un analista territoriale. Dato il contesto JSON di un comune (profilo, "
    "investimenti, segnali, gap di dato), scrivi una sintesi in italiano (~180 parole) "
    "con paragrafi per: profilo del territorio, investimenti pubblici, servizi/accessibilità, "
    "segnali rilevanti e principali gap di dato. Prosa concreta, niente elenchi di metadati.\n\n"
    "Contesto:\n"
)


def _fallback(context: dict[str, Any]) -> str:
    name = (context.get("place") or {}).get("name", "il comune")
    pop = (context.get("profilo") or {}).get("population", {}).get("total")
    inv = (context.get("investimenti") or {}).get("finanziamento_totale")
    parts = [f"Profilo: {name}" + (f", popolazione {pop}." if pop else ".")]
    if inv:
        parts.append(f"Investimenti pubblici tracciati: € {inv:,.0f}.")
    parts.append("Sintesi generata in modalità offline (provider LLM non configurato).")
    return " ".join(parts)


async def generate_report_narrative(settings: Settings, *, context: dict[str, Any]) -> str:
    text = await complete(
        settings,
        prompt=_PROMPT + json.dumps(context, ensure_ascii=False),
        max_tokens=700,
    )
    return text or _fallback(context)
