"""Pre-analisi di un'area tematica — gli "spunti" mostrati appena scegli il tema.

Prima ancora che l'utente scriva, l'Idea Lab perlustra l'area: quali dataset
ci sono (con qualità), quali progetti simili sono già stati finanziati, e da
lì propone 3-4 direzioni d'idea concrete. Un solo passaggio LLM opzionale
(`llm.complete()`, R11) con fallback deterministico: gli spunti offline sono
costruiti dai titoli dei dataset trovati.
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..llm import complete
from .coach import _datasets_block, _funding_block, parse_coach_json
from .discovery import discover_datasets, discover_funding
from .models import AREAS, IdeaScoutRequest, IdeaScoutResponse, IdeaSpunto

log = logging.getLogger("opendata-backend.ideas")

_SCOUT_SYSTEM = (
    "Suggerisci direzioni progettuali per un ente pubblico italiano a partire "
    "dai soli dataset aperti e progetti finanziati forniti. Concretezza: ogni "
    "spunto deve poggiare su dataset citati per titolo, niente idee generiche."
)


def _offline_spunti(area: str, datasets: list) -> list[IdeaSpunto]:
    label = AREAS[area]["label"].lower()
    top = [d.title for d in datasets[:3]]
    base = top[0] if top else f"i dataset aperti dell'area {label}"
    spunti = [
        IdeaSpunto(
            titolo=f"Servizio informativo al cittadino ({label})",
            descrizione=f"Un servizio consultabile costruito su {base}, con dati sempre aggiornati e fonte citata.",
        ),
        IdeaSpunto(
            titolo="Cruscotto di monitoraggio per l'ente",
            descrizione=(
                "Indicatori ricavati dai dataset disponibili "
                f"({', '.join(top) if top else 'da individuare'}), per orientare le decisioni."
            ),
        ),
        IdeaSpunto(
            titolo="Analisi dei divari territoriali",
            descrizione=f"Confronto tra comuni/zone sull'area {label} per indirizzare gli interventi dove servono.",
        ),
    ]
    return spunti


async def scout_area(settings: Settings, req: IdeaScoutRequest) -> IdeaScoutResponse:
    datasets = await discover_datasets(settings, area=req.area, challenge_text="")
    funding = await discover_funding(settings, area=req.area)

    prompt = (
        f"AREA: {AREAS[req.area]['label']} | TERRITORIO: {req.territory or 'Puglia'}\n\n"
        f"DATASET DISPONIBILI (con qualità):\n{_datasets_block(datasets)}\n\n"
        f"PROGETTI COMPARABILI GIÀ FINANZIATI (OpenCoesione):\n{_funding_block(funding)}\n\n"
        "Proponi le direzioni d'idea PIÙ concrete permesse da questi dati (3-4), "
        "diverse tra loro (servizio al cittadino / strumento per l'ente / "
        "monitoraggio / analisi). Rispondi SOLO con JSON: "
        '{"spunti": [{"titolo": "<max 8 parole>", "descrizione": "<1-2 frasi: '
        "cosa fa e su QUALI dataset si fonda, citati per titolo>\"}]}"
    )
    raw = await complete(
        settings, prompt=prompt, system=_SCOUT_SYSTEM, max_tokens=800, temperature=0.4
    )
    spunti: list[IdeaSpunto] = []
    offline = True
    if raw is not None and (data := parse_coach_json(raw)):
        for s in (data.get("spunti") or [])[:4]:
            titolo = str((s or {}).get("titolo") or "").strip()
            if titolo:
                spunti.append(
                    IdeaSpunto(titolo=titolo, descrizione=str(s.get("descrizione") or "").strip())
                )
        offline = not spunti
    if not spunti:
        if raw is not None:
            log.warning("ideas scout: risposta LLM non parsabile, uso il fallback")
        spunti = _offline_spunti(req.area, datasets)

    return IdeaScoutResponse(
        datasets=datasets, funding=funding, spunti=spunti, offline=offline
    )
