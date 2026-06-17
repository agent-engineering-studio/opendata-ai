"""Test della modalità Territorio (resolve_place + build_profile) con OSM mockato."""

from __future__ import annotations

import opendata_core.territory.profile as profile_mod
import opendata_core.territory.resolve as resolve_mod
from opendata_core.territory import build_profile, resolve_place


async def test_resolve_place_maps_geocode(monkeypatch) -> None:
    async def fake_boundary(name, **_):
        return {"name": "Gioia del Colle", "lat": 40.7986, "lon": 16.9268,
                "geojson": {"type": "Polygon", "coordinates": []}}

    monkeypatch.setattr(resolve_mod, "geocode_boundary", fake_boundary)
    place = await resolve_place("Gioia del Colle", istat_code="072021")
    assert place is not None
    assert place.istat_code == "072021"
    assert place.lat == 40.7986
    assert place.geojson["type"] == "Polygon"


async def test_resolve_place_none_on_no_match(monkeypatch) -> None:
    async def none_boundary(name, **_):
        return None

    monkeypatch.setattr(resolve_mod, "geocode_boundary", none_boundary)
    assert await resolve_place("Atlantide") is None


async def test_build_profile_with_mocked_overpass(monkeypatch) -> None:
    async def fake_commercial(**_):
        return {"supermarket": 3, "restaurant": 12, "totale": 40}

    async def fake_tourism(**_):
        return {"hotel": 2, "museum": 1, "totale": 5}

    monkeypatch.setattr(profile_mod, "overpass_commercial_counts", fake_commercial)
    monkeypatch.setattr(profile_mod, "overpass_tourism_counts", fake_tourism)

    place = profile_mod.PlaceRef(name="Gioia del Colle", istat_code="072021", lat=40.8, lon=16.9)
    prof = await build_profile(place, population=27000)
    assert prof.population == {"total": 27000}
    assert prof.business["totale"] == 40
    assert prof.tourism["hotel"] == 2
    signals = prof.as_signals()
    assert set(signals) == {"population", "business", "tourism", "work"}


async def test_build_profile_failsafe_without_coords(monkeypatch) -> None:
    place = profile_mod.PlaceRef(name="X", lat=None, lon=None)
    prof = await build_profile(place, population=None)
    assert prof.business == {}
    assert prof.tourism == {}
    assert prof.population == {}
