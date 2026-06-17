"""Test dei connettori Fase 3: Open-Meteo, GTFS, Wikidata, portali."""

from __future__ import annotations

import io
import zipfile

from pytest_httpx import HTTPXMock

from opendata_core.gtfs import parse_stops
from opendata_core.meteo import forecast
from opendata_core.meteo.client import describe_weather
from opendata_core.portals import get_portal
from opendata_core.wikidata import comune_by_istat


# ── Open-Meteo ──────────────────────────────────────────────────────


def test_describe_weather() -> None:
    assert describe_weather(0) == ("sereno", True)
    assert describe_weather(61)[1] is False
    assert describe_weather(None) == ("n/d", False)


async def test_forecast_parses_daily(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={
        "daily": {
            "time": ["2026-06-18", "2026-06-19"],
            "weathercode": [0, 61],
            "temperature_2m_max": [30.0, 22.0],
            "temperature_2m_min": [20.0, 16.0],
            "precipitation_sum": [0.0, 8.0],
        }
    })
    fc = await forecast(40.8, 16.9, days=2)
    assert fc["license"].startswith("CC-BY")
    assert len(fc["daily"]) == 2
    assert fc["daily"][0]["outdoor_ok"] is True
    assert fc["daily"][1]["label"] == "pioggia debole"


# ── GTFS ────────────────────────────────────────────────────────────


def _gtfs_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "stops.txt",
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "S1,Stazione,40.80,16.92\n"
            "S2,Piazza,40.79,16.93\n"
            "BAD,NoCoord,,\n",
        )
    return buf.getvalue()


def test_parse_stops_skips_invalid() -> None:
    stops = parse_stops(_gtfs_zip())
    assert len(stops) == 2
    assert stops[0].stop_id == "S1"
    assert stops[0].lat == 40.80


def test_parse_stops_empty_without_stops_file() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("agency.txt", "agency_id\nA1\n")
    assert parse_stops(buf.getvalue()) == []


# ── Wikidata ────────────────────────────────────────────────────────


async def test_wikidata_comune(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"results": {"bindings": [{
        "item": {"value": "http://www.wikidata.org/entity/Q42"},
        "itemLabel": {"value": "Gioia del Colle"},
        "population": {"value": "27889"},
        "area": {"value": "206.5"},
    }]}})
    out = await comune_by_istat("072021")
    assert out is not None
    assert out["qid"] == "Q42"
    assert out["population"] == 27889
    assert out["area_km2"] == 206.5


async def test_wikidata_none_on_empty(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(json={"results": {"bindings": []}})
    assert await comune_by_istat("000000") is None


# ── Portali ─────────────────────────────────────────────────────────


def test_portal_registry() -> None:
    p = get_portal("puglia")
    assert p is not None
    assert p.base_url == "https://dati.puglia.it"
    assert get_portal("inesistente") is None
