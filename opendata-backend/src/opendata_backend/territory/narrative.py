"""Narrazione del report territoriale via Claude Sonnet (fail-safe offline)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

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
    parts.append("Sintesi generata in modalità offline (ANTHROPIC_API_KEY non configurata).")
    return " ".join(parts)


async def generate_report_narrative(*, model: str, context: dict[str, Any]) -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _fallback(context)
    try:
        import anthropic

        client = anthropic.AsyncAnthropic()
        msg = await client.messages.create(
            model=model,
            max_tokens=700,
            messages=[{"role": "user", "content": _PROMPT + json.dumps(context, ensure_ascii=False)}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return text.strip() or _fallback(context)
    except Exception as exc:  # noqa: BLE001
        log.warning("narrativa territorio non disponibile: %s", exc)
        return _fallback(context)
