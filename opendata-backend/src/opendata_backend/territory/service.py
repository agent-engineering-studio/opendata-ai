"""Orchestrazione del report territoriale (modello canonico + narrazione Sonnet).

resolve luogo → profilo (signals) → investimenti (OpenCoesione) → persisti
(place/signals/investment/feature_store) → report strutturato + narrazione →
persisti in territory_reports. Cache profilo in feature_store (GET /profile).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from opendata_core.territory import build_profile, resolve_place
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db.repositories import territory as repo
from ..features.engineering import compute_features
from ..usecases.apriqui import score_categories
from .investments import fetch_investments, persist_investments, summarize_investments
from .narrative import generate_report_narrative

log = logging.getLogger("opendata-backend.territory")


def _gap_analysis(
    profile_signals: dict[str, Any], inv_summary: dict[str, Any], *, pug_published: bool | None = None,
) -> list[str]:
    gaps: list[str] = []
    if not profile_signals.get("population"):
        gaps.append("Popolazione non disponibile in anagrafica ISTAT.")
    if not profile_signals.get("business") and not profile_signals.get("tourism"):
        gaps.append("Segnali OSM (commercio/turismo) non recuperati.")
    if inv_summary.get("n_progetti", 0) == 0:
        gaps.append("Nessun progetto OpenCoesione tracciato per il comune.")
    if not profile_signals.get("work"):
        gaps.append("Dati su lavoro/occupazione non ancora integrati (fase successiva).")
    # #129: il PUG serve alla riconciliazione del suolo (destinazione urbanistica).
    # Se il portale regionale è raggiungibile ma non lo espone come open data, è una
    # domanda di riuso non soddisfatta + un invito alla pubblicazione (pivot: la fonte
    # ufficiale è il dato aperto, non un documento caricato). `None` = non verificabile.
    if pug_published is False:
        gaps.append(
            "PUG (zonizzazione urbanistica) non pubblicato come open data: pubblicalo come "
            "dataset DCAT-AP_IT — è una fonte ufficiale richiesta dall'analisi del territorio."
        )
    return gaps


async def _pug_published(istat_code: str, comune_nome: str | None) -> bool | None:
    """Il PUG del comune è pubblicato come open data interrogabile?

    True se trovato, False se il portale regionale è noto ma non lo espone, None se
    non verificabile (nessun portale regionale mappato). Fail-safe: mai solleva."""
    from ..config_files import portali_regionali

    prov = str(istat_code or "").strip().zfill(6)[:3]
    portale = (portali_regionali().get("province_ckan") or {}).get(prov)
    if not portale or not comune_nome:
        return None
    try:
        from opendata_core.pug import fetch_zoning

        return (await fetch_zoning(comune_nome=comune_nome, base_url=portale)) is not None
    except Exception:  # noqa: BLE001 — non verificabile → nessuna penalità falsa
        return None


async def build_report(
    session: AsyncSession, *, istat_code: str, temi: list[str] | None,
    anno_da: int | None, anno_a: int | None, settings: Settings,
) -> dict[str, Any]:
    """Genera, persiste e ritorna il report territoriale del comune."""
    anag = await repo.comune_anagrafica(session, istat_code)
    name = anag.nome if anag else istat_code
    population = anag.popolazione if anag else None

    place_ref = None
    try:
        place_ref = await resolve_place(name, istat_code=istat_code)
    except Exception as exc:  # noqa: BLE001
        log.warning("resolve_place fallito per %s: %s", istat_code, exc)

    if place_ref is not None:
        profile = await build_profile(place_ref, population=population)
    else:
        from opendata_core.territory import TerritoryProfile

        profile = TerritoryProfile(
            population={"total": population} if population is not None else {}
        )

    inv = await fetch_investments(cod_comune=istat_code)
    inv_summary = summarize_investments(inv["projects"])

    now = datetime.now(timezone.utc)
    place = await repo.upsert_place(session, istat_code=istat_code, name=name)
    signals = profile.as_signals()
    await repo.save_signals(session, place_id=place.id, signals=signals, observed_at=now)
    await persist_investments(session, place_id=place.id, projects=inv["projects"], observed_at=now)

    # Feature store (Layer 3) + idee di sviluppo dall'output ApriQui (Fase 3).
    feat = compute_features(
        business=signals.get("business"), tourism=signals.get("tourism"),
        mobility=[], population=population,
    )
    features = {
        "profile": signals, "investments": inv_summary,
        "features": feat["features"], "feature_gaps": feat["gaps"],
    }
    await repo.upsert_feature_store(session, place_id=place.id, features=features, computed_at=now)

    ideas = score_categories(
        business=signals.get("business", {}), features=feat["features"], population=population
    )[:3]
    idee_sviluppo = [
        {
            "category": i["category"], "score": i["score"],
            "rationale": f"opportunità {i['opportunity']} · domanda {i['demand']} · "
                         f"accessibilità {i['accessibility']}",
        }
        for i in ideas
    ]

    sezioni = {
        "profilo": signals,
        "investimenti": inv_summary,
        "servizi_accessibilita": {
            "commercio": signals.get("business", {}),
            "turismo_cultura": signals.get("tourism", {}),
        },
        "segnali": signals,
        "idee_sviluppo": idee_sviluppo,  # da ApriQui (Fase 3)
        "gap_dato": _gap_analysis(signals, inv_summary, pug_published=await _pug_published(istat_code, name)),
    }
    context = {
        "place": {"istat_code": istat_code, "name": name},
        "filtri": {"temi": temi or [], "anno_da": anno_da, "anno_a": anno_a},
        "profilo": signals,
        "investimenti": inv_summary,
        "gap_dato": sezioni["gap_dato"],
    }
    narrativa = await generate_report_narrative(settings, context=context)

    payload = {
        "place": {"id": place.id, "istat_code": istat_code, "name": name},
        "generato_il": now.isoformat(),
        "filtri": {"temi": temi or [], "anno_da": anno_da, "anno_a": anno_a},
        "narrativa": narrativa,
        "sezioni": sezioni,
    }
    await repo.save_report(session, place_id=place.id, payload=payload, created_at=now)
    await session.commit()
    return payload


async def get_profile(session: AsyncSession, istat_code: str) -> dict[str, Any] | None:
    """Profilo cache-ato del comune (feature_store). None se non ancora calcolato."""
    place = await repo.get_place_by_istat(session, istat_code)
    if place is None:
        return None
    fs = await repo.get_feature_store(session, place.id)
    if fs is None:
        return None
    return {
        "place": {"id": place.id, "istat_code": place.istat_code, "name": place.name},
        "computed_at": fs.computed_at.isoformat() if fs.computed_at else None,
        "features": fs.features_jsonb,
    }
