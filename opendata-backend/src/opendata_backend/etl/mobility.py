"""Ingest GTFS → tabella canonica mobility_node (fermate del TPL).

Registra il raw, filtra le fermate vicine al comune e (idempotente) rigenera i
MobilityNode source='gtfs' del place.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime

from opendata_core.gtfs import GtfsStop, fetch_stops
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.territory_models import MobilityNode
from .raw import record_raw


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanza in km tra due punti (formula dell'emisenoverso)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def ingest_gtfs_stops(
    session: AsyncSession,
    *,
    place_id: int,
    stops: list[GtfsStop],
    observed_at: datetime,
    center: tuple[float, float] | None = None,
    radius_km: float = 10.0,
    license: str = "GTFS feed (licenza per ente)",
    source: str = "gtfs",
) -> int:
    """Registra il raw + rigenera i mobility_node del place dalle fermate (filtrate per vicinanza)."""
    await record_raw(
        session, source=source, dataset_id=f"place:{place_id}",
        payload={"stops": [asdict(s) for s in stops]}, license=license,
    )

    selected: list[tuple[GtfsStop, float | None]] = []
    for s in stops:
        dist = None
        if center is not None:
            dist = haversine_km(center[0], center[1], s.lat, s.lon)
            if dist > radius_km:
                continue
        selected.append((s, dist))

    await session.execute(
        delete(MobilityNode).where(MobilityNode.place_id == place_id, MobilityNode.source == source)
    )
    for s, dist in selected:
        session.add(MobilityNode(
            place_id=place_id, source=source, observed_at=observed_at,
            payload_jsonb={
                "stop_id": s.stop_id, "name": s.name, "lat": s.lat, "lon": s.lon,
                "distance_km": round(dist, 3) if dist is not None else None,
            },
        ))
    await session.flush()
    return len(selected)


async def ingest_gtfs_url(
    session: AsyncSession, *, place_id: int, url: str, observed_at: datetime,
    center: tuple[float, float] | None = None, radius_km: float = 10.0,
    license: str = "GTFS feed (licenza per ente)",
) -> int:
    """Scarica un feed GTFS e ne ingerisce le fermate per il place."""
    stops = await fetch_stops(url)
    return await ingest_gtfs_stops(
        session, place_id=place_id, stops=stops, observed_at=observed_at,
        center=center, radius_km=radius_km, license=license,
    )
