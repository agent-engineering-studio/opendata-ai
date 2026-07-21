"""Orchestrazione del Copilota Open Data (#222, backend di #170).

Espone le funzioni consumate dal router `/dataplan/{istat}/*`, **riusando** i
motori puri di `opendata_core.dataplan` (nessuna logica nuova) e le capability
esistenti (maturità, LLM one-shot, connettori). Fail-safe: le fonti live non
raggiungibili degradano a sezione "non disponibile", mai 500. L'LLM è opzionale
(R11): senza provider, politica/brief usano il fallback deterministico dei motori.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opendata_core.dataplan import (
    accompaniment_state,
    build_piano,
    build_politica,
    checklist_for,
    load_catalog,
    prioritize,
    render_piano_markdown,
    render_politica_markdown,
)

from ..config import Settings
from ..db.models import ComuneAnagrafica
from ..llm import complete
from .repository import save_plan

log = logging.getLogger("opendata-backend.dataplan")


async def _ente_nome(session: AsyncSession | None, istat_code: str) -> str:
    """Nome del comune dall'anagrafica; fallback al codice ISTAT."""
    if session is None:
        return istat_code
    candidates = {istat_code, istat_code.zfill(6)}
    nome = await session.scalar(
        select(ComuneAnagrafica.nome).where(ComuneAnagrafica.cod_comune.in_(candidates))
    )
    return str(nome) if nome else istat_code


def _gia_aperto_nazionale() -> list[dict[str, Any]]:
    """Adempimenti già aperti a livello nazionale (dal catalogo): si linkano."""
    out = []
    for c in load_catalog():
        if c.gia_aperto is not None:
            out.append({
                "id": c.id, "nome": c.nome, "fonte": c.gia_aperto.fonte,
                "connettore": c.gia_aperto.connettore,
            })
    return out


async def diagnosi(session: AsyncSession, settings: Settings, *, istat_code: str) -> dict[str, Any]:
    """Fotografia "quanto sei aperto oggi": baseline maturità (se esiste) + adempimenti
    nazionali già aperti. Non lancia un harvest live: legge ciò che c'è (fail-safe)."""
    ente = await _ente_nome(session, istat_code)
    pubblicato: dict[str, Any] | None = None
    hint: str | None = None
    try:
        from ..db.repositories import maturity as mrepo
        from ..db.territory_models import Entity
        ent = await session.scalar(select(Entity).where(Entity.name == ente))
        if ent is not None:
            latest = await mrepo.latest_assessment(session, ent.id)
            if latest is not None:
                pubblicato = {
                    "n_dataset": int((latest.details_jsonb or {}).get("n_datasets") or 0),
                    "overall": float(latest.score_overall or 0), "level": latest.level,
                }
    except Exception:  # noqa: BLE001 — baseline è un di più, mai bloccante
        log.info("dataplan.diagnosi: baseline maturità non disponibile per %s", istat_code)
    if pubblicato is None:
        hint = "Baseline non ancora calcolata: esegui /maturity/assess per l'ente."
    # Accompagnamento attivo (#184): stato zero→maturo + percorso ente-specifico.
    stato = accompaniment_state(
        n_dataset=int((pubblicato or {}).get("n_dataset") or 0),
        overall=(pubblicato or {}).get("overall"),
    )
    return {
        "istat": istat_code,
        "comune": ente,
        "pubblicato": pubblicato,
        "hint": hint,
        "gia_aperto_nazionale": _gia_aperto_nazionale(),
        "accompagnamento": stato.model_dump(),
    }


def inventario(*, istat_code: str) -> dict[str, Any]:
    """Catalogo dei dataset candidati (D1) — deterministico, no rete."""
    voci = []
    for c in load_catalog():
        d = c.model_dump()
        d["gia_aperto_nazionale"] = c.gia_aperto is not None
        voci.append(d)
    return {"istat": istat_code, "candidati": voci, "totale": len(voci)}


async def piano(session: AsyncSession, *, istat_code: str) -> dict[str, Any]:
    """Candidati prioritizzati (D2) + piano di pubblicazione (D3). GET puro."""
    ente = await _ente_nome(session, istat_code)
    # reuse_boost dall'anello Fase 5 (domanda di riuso non soddisfatta) è un
    # affinamento futuro: il segnale di riuso è già nel catalogo (`sblocca`).
    ranked = prioritize(load_catalog())
    pl = build_piano(ranked, ente=ente)
    return {
        "istat": istat_code,
        "ente": ente,
        "ranking": [r.model_dump() for r in ranked],
        "piano": pl.model_dump(),
        "piano_markdown": render_piano_markdown(pl),
    }


async def _llm_sezioni(settings: Settings, ente: str, sezioni: list[Any]) -> tuple[list[dict], str]:
    """Riscrive la prosa delle sezioni via LLM (best-effort). Fallback: testo deterministico."""
    out: list[dict[str, Any]] = []
    generato_con = "offline"
    for s in sezioni:
        testo = s.testo
        prompt = (
            f"Riscrivi in italiano amministrativo chiaro e conciso questa sezione della "
            f"Politica Open Data del Comune di {ente}. Mantieni i riferimenti normativi e "
            f"non inventare fatti. Sezione «{s.titolo}»:\n{s.testo}"
        )
        try:
            llm = await complete(settings, prompt=prompt, max_tokens=400)
        except Exception:  # noqa: BLE001 — LLM best-effort
            llm = None
        if llm and llm.strip():
            testo = llm.strip()
            generato_con = "llm"
        out.append({"titolo": s.titolo, "testo": testo})
    return out, generato_con


async def genera_politica(
    session: AsyncSession, settings: Settings, *, istat_code: str, licenza: str | None = None,
) -> dict[str, Any]:
    """Bozza di Politica Open Data (LLM + fallback offline) e la persiste (append-only)."""
    ente = await _ente_nome(session, istat_code)
    pol = build_politica(ente=ente, licenza=licenza) if licenza else build_politica(ente=ente)
    sezioni, generato_con = await _llm_sezioni(settings, ente, pol.sezioni)
    payload = {
        "titolo": pol.titolo, "licenza": pol.licenza, "sezioni": sezioni,
        "generato_con": generato_con,
        "markdown": render_politica_markdown(pol),  # versione deterministica
    }
    try:
        await save_plan(session, istat_code=istat_code, ente=ente, tipo="politica", payload=payload)
        await session.commit()
    except Exception:  # noqa: BLE001 — la persistenza è storicizzazione, non blocca la risposta
        await session.rollback()
        log.warning("dataplan: persistenza politica fallita per %s", istat_code, exc_info=True)
    return {"istat": istat_code, "ente": ente, **payload}


async def brief(
    session: AsyncSession, settings: Settings, *, istat_code: str, candidate_id: str,
) -> dict[str, Any] | None:
    """Export brief operativo per UN dataset candidato: passi + privacy + DCAT."""
    ente = await _ente_nome(session, istat_code)
    cand = next((c for c in load_catalog() if c.id == candidate_id), None)
    if cand is None:
        return None
    cl = checklist_for(cand)
    # metadati DCAT + cadenza/ufficio dalla voce di piano corrispondente
    voce = next((v for v in build_piano(prioritize([cand]), ente=ente).voci), None)
    passi_prod = list(cl.passi)
    prosa = None
    prompt = (
        f"Scrivi un'istruzione operativa breve per l'ufficio del Comune di {ente} su come "
        f"pubblicare come open data «{cand.nome}» (fonte: {cand.fonte_interna}). Rispetta questi "
        f"passi privacy: {'; '.join(cl.passi)}. Non inventare campi."
    )
    try:
        prosa = await complete(settings, prompt=prompt, max_tokens=400)
    except Exception:  # noqa: BLE001
        prosa = None
    return {
        "istat": istat_code, "ente": ente, "candidate_id": cand.id, "nome": cand.nome,
        "ufficio": voce.ufficio if voce else None,
        "cadenza": voce.cadenza if voce else None,
        "privacy": cl.model_dump(),
        "metadati_dcat": voce.metadati_dcat if voce else None,
        "passi": passi_prod,
        "istruzione": prosa.strip() if prosa and prosa.strip() else None,
        "generato_con": "llm" if prosa and prosa.strip() else "offline",
    }
