"""Parsing GTFS → fermate. Solo stdlib (zipfile + csv); fetch via httpx.

GTFS è uno zip con `stops.txt` (stop_id, stop_name, stop_lat, stop_lon). Qui
estraiamo le fermate, che il backend normalizza nella tabella `mobility_node`.
La licenza del feed va tracciata dal chiamante (varia per ente).
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass

import httpx

HTTP_TIMEOUT = 60.0


@dataclass(frozen=True)
class GtfsStop:
    stop_id: str
    name: str
    lat: float
    lon: float


def parse_stops(zip_bytes: bytes) -> list[GtfsStop]:
    """Estrae le fermate da uno zip GTFS in memoria. Righe invalide ignorate."""
    stops: list[GtfsStop] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name = next((n for n in zf.namelist() if n.endswith("stops.txt")), None)
        if name is None:
            return stops
        with zf.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8-sig", newline="")
            for row in csv.DictReader(text):
                try:
                    stops.append(GtfsStop(
                        stop_id=str(row["stop_id"]).strip(),
                        name=str(row.get("stop_name") or "").strip(),
                        lat=float(row["stop_lat"]),
                        lon=float(row["stop_lon"]),
                    ))
                except (KeyError, TypeError, ValueError):
                    continue
    return stops


async def fetch_stops(url: str) -> list[GtfsStop]:
    """Scarica un feed GTFS (zip) e ne estrae le fermate."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return parse_stops(resp.content)
