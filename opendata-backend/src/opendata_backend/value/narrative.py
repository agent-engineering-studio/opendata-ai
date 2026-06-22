"""Narrazione di valore: problema → dato → servizio → beneficiario.

Standalone (niente orchestratore). Usa il provider LLM risolto. Fail-safe:
senza provider configurato ritorna una narrazione-template deterministica →
endpoint e test funzionano offline.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..config import Settings
from ..llm import complete

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
        f"(Narrazione sintetica: provider LLM non configurato.)"
    )


async def generate_narrative(settings: Settings, *, context: dict[str, Any]) -> str:
    """Narrazione di valore via il provider LLM risolto; template se assente."""
    text = await complete(
        settings,
        prompt=_PROMPT + json.dumps(context, ensure_ascii=False),
        max_tokens=512,
    )
    return text or _fallback(context)
