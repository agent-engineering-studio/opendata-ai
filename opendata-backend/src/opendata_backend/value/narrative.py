"""Narrazione di valore via Claude Sonnet: problema → dato → servizio → beneficiario.

Standalone (niente orchestratore). Fail-safe: senza ANTHROPIC_API_KEY ritorna una
narrazione-template deterministica → endpoint e test funzionano offline.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("opendata-backend.value.narrative")

_PROMPT = (
    "Sei un analista di open data. Dato il contesto JSON di un dataset/tema, scrivi una "
    "narrazione di valore BREVE (max ~150 parole) in italiano, articolata in quattro passaggi "
    "chiari: 1) Problema, 2) Dato (come lo affronta), 3) Servizio realizzabile, 4) Beneficiario. "
    "Niente elenco puntato di metadati, solo prosa concreta.\n\nContesto:\n"
)


def _fallback(context: dict[str, Any]) -> str:
    title = context.get("title") or context.get("dataset") or "il dataset"
    return (
        f"Problema: molte decisioni locali mancano di dati strutturati. "
        f"Dato: {title} fornisce una base riutilizzabile. "
        f"Servizio: può alimentare cruscotti, mappe o app di pubblica utilità. "
        f"Beneficiario: cittadini, imprese e amministrazione. "
        f"(Narrazione sintetica: ANTHROPIC_API_KEY non configurata.)"
    )


async def generate_narrative(*, model: str, context: dict[str, Any]) -> str:
    """Narrazione di valore. Usa Sonnet se la chiave è presente, altrimenti template."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _fallback(context)
    try:
        import anthropic

        client = anthropic.AsyncAnthropic()
        msg = await client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": _PROMPT + json.dumps(context, ensure_ascii=False)}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return text.strip() or _fallback(context)
    except Exception as exc:  # noqa: BLE001 — narrazione best-effort
        log.warning("narrativa Sonnet non disponibile: %s", exc)
        return _fallback(context)
