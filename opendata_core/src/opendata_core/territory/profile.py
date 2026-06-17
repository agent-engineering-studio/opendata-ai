"""Costruzione del profilo canonico del territorio (segnali da OSM + popolazione iniettata)."""

from __future__ import annotations

import logging

from ..osm.client import overpass_commercial_counts, overpass_tourism_counts
from .models import PlaceRef, TerritoryProfile

log = logging.getLogger("opendata-core.territory.profile")

DEFAULT_RADIUS_M = 5000


async def build_profile(
    place: PlaceRef, *, population: int | None = None, radius_m: int = DEFAULT_RADIUS_M
) -> TerritoryProfile:
    """Profilo del comune: population (iniettata da ISTAT) + conteggi POI OSM.

    Fail-safe: se Overpass non risponde, i segnali corrispondenti restano vuoti.
    """
    business: dict[str, int] = {}
    tourism: dict[str, int] = {}
    if place.lat is not None and place.lon is not None:
        around = (place.lat, place.lon, radius_m)
        try:
            business = await overpass_commercial_counts(around=around)
        except Exception as exc:  # noqa: BLE001
            log.warning("commercial_counts non disponibili: %s", exc)
        try:
            tourism = await overpass_tourism_counts(around=around)
        except Exception as exc:  # noqa: BLE001
            log.warning("tourism_counts non disponibili: %s", exc)

    return TerritoryProfile(
        population={"total": population} if population is not None else {},
        business=business,
        tourism=tourism,
        work={},  # occupazione/lavoro: fase successiva (ISTAT), placeholder per ora
    )
