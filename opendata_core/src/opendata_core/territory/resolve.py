"""Risoluzione del luogo: nome → centroide + confine GeoJSON via OSM/Nominatim.

Il mapping codice ISTAT → nome vive nel backend (ComuneAnagrafica): qui il nome è
passato dal chiamante, che propaga anche l'istat_code in PlaceRef.
"""

from __future__ import annotations

from ..osm.client import geocode_boundary
from .models import PlaceRef


async def resolve_place(name: str, *, istat_code: str | None = None) -> PlaceRef | None:
    """Risolve un comune (per nome) a PlaceRef con geometria. None se nessun match."""
    hit = await geocode_boundary(name)
    if not hit:
        return None
    return PlaceRef(
        name=hit.get("name") or name,
        istat_code=istat_code,
        lat=hit.get("lat"),
        lon=hit.get("lon"),
        geojson=hit.get("geojson"),
    )
