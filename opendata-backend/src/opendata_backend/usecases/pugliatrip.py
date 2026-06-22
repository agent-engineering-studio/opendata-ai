"""PugliaTrip Brain — itinerari meteo-aware (POI + mobilità + Open-Meteo).

"PugliaTrip" è il nome del prodotto, ma l'implementazione è REGION-AGNOSTICA:
funziona per qualunque comune italiano (resolve per nome via anagrafica, meteo per
lat/lon, landmark per bbox). Nessun riferimento hardcoded alla Puglia.

Core PURO (`build_itinerary`): assegna i POI ai giorni in base al meteo (outdoor nei
giorni belli, musei/coperti quando piove). Il service recupera POI (OSM), meteo
(Open-Meteo) e mobilità (mobility_node) ed è fail-safe; la spiegazione è via Sonnet.
"""

from __future__ import annotations

import logging
from typing import Any

from opendata_core.meteo import forecast
from opendata_core.osm.client import overpass_tourism_landmarks
from opendata_core.territory import resolve_place
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db.repositories import territory as repo
from ..db.territory_models import MobilityNode
from .llm import explain

log = logging.getLogger("opendata-backend.usecases.pugliatrip")

# Tipi OSM considerati "al chiuso" (adatti alle giornate di pioggia).
_INDOOR_KINDS = {"museum", "gallery", "artwork", "aquarium"}
_POIS_PER_DAY = 2


def _is_indoor(kind: str) -> bool:
    return kind.strip().lower() in _INDOOR_KINDS


def build_itinerary(
    pois: list[dict[str, str]], forecast_daily: list[dict[str, Any]], *, n_stops: int | None = None
) -> list[dict[str, Any]]:
    """Assegna i POI ai giorni di previsione in base al meteo. Funzione PURA.

    Giorno bello (outdoor_ok) → preferisci POI all'aperto; pioggia → POI al chiuso.
    Nessun POI ripetuto; ~`_POIS_PER_DAY` per giorno (o n_stops).
    """
    indoor = [p for p in pois if _is_indoor(p.get("kind", ""))]
    outdoor = [p for p in pois if not _is_indoor(p.get("kind", ""))]
    per_day = n_stops or _POIS_PER_DAY
    plan: list[dict[str, Any]] = []
    for day in forecast_daily:
        primary, secondary = (outdoor, indoor) if day.get("outdoor_ok") else (indoor, outdoor)
        chosen: list[dict[str, str]] = []
        for pool in (primary, secondary):
            while pool and len(chosen) < per_day:
                chosen.append(pool.pop(0))
        plan.append({
            "date": day.get("date"),
            "weather": {"label": day.get("label"), "tmax": day.get("tmax"),
                        "precip": day.get("precip"), "outdoor_ok": day.get("outdoor_ok")},
            "pois": chosen,
        })
    return plan


async def run_pugliatrip(
    session: AsyncSession, *, istat_code: str, days: int, settings: Settings
) -> dict[str, Any]:
    """Itinerario meteo-aware per il comune + spiegazione. Fail-safe sulle fonti live."""
    anag = await repo.comune_anagrafica(session, istat_code)
    name = anag.nome if anag else istat_code

    place_ref = None
    try:
        place_ref = await resolve_place(name, istat_code=istat_code)
    except Exception as exc:  # noqa: BLE001
        log.warning("resolve_place fallito (%s): %s", istat_code, exc)

    pois: list[dict[str, str]] = []
    forecast_daily: list[dict[str, Any]] = []
    if place_ref and place_ref.lat is not None and place_ref.lon is not None:
        lat, lon = place_ref.lat, place_ref.lon
        d = 0.05
        try:
            pois = await overpass_tourism_landmarks(bbox=(lat - d, lon - d, lat + d, lon + d), limit=20)
        except Exception as exc:  # noqa: BLE001
            log.warning("landmarks OSM non disponibili: %s", exc)
        try:
            fc = await forecast(lat, lon, days=days)
            forecast_daily = fc.get("daily", [])
        except Exception as exc:  # noqa: BLE001
            log.warning("meteo non disponibile: %s", exc)

    itinerary = build_itinerary(pois, forecast_daily)

    # Mobilità: fermate note del comune (per "raggiungibile in TPL").
    place = await repo.get_place_by_istat(session, istat_code)
    n_stops = 0
    if place is not None:
        rows = (
            await session.execute(select(MobilityNode).where(MobilityNode.place_id == place.id))
        ).scalars().all()
        n_stops = len(rows)

    fallback = (
        f"Itinerario per {name}: {len(itinerary)} giorni pianificati su "
        f"{len(pois)} luoghi, adattati al meteo (musei nei giorni di pioggia). "
        f"{n_stops} fermate TPL note per gli spostamenti."
    )
    explanation = await explain(
        settings,
        instructions=(
            "Sei una guida turistica locale del comune indicato (qualunque regione italiana). "
            "Spiega in italiano (~120 parole) l'itinerario proposto, evidenziando come è stato "
            "adattato al meteo (attività all'aperto nei giorni sereni, musei/luoghi al chiuso "
            "quando piove) e come muoversi. Concreto, riferito al territorio del comune."
        ),
        context={"comune": name, "itinerario": itinerary, "fermate_tpl": n_stops},
        fallback=fallback,
    )

    center = (
        {"lat": place_ref.lat, "lon": place_ref.lon}
        if place_ref and place_ref.lat is not None and place_ref.lon is not None
        else None
    )
    return {
        "place": {"istat_code": istat_code, "name": name},
        "center": center,
        "n_pois": len(pois),
        "n_stops": n_stops,
        "itinerary": itinerary,
        "explanation": explanation,
    }
