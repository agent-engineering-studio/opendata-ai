"""Smoke tests for the OSM MCP tool layer.

These tests mock httpx with respx, so no network traffic is required.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from opendata_core.osm.settings import osm_settings as settings

from osm_mcp import tools


@pytest.mark.asyncio
@respx.mock
async def test_geocode_address():
    respx.get(f"{settings.NOMINATIM_URL}/search").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "display_name": "Milan, Italy",
                    "lat": "45.4642",
                    "lon": "9.19",
                    "type": "city",
                    "class": "place",
                    "importance": 0.9,
                    "boundingbox": ["45.3", "45.6", "9.0", "9.3"],
                    "address": {"city": "Milan", "country": "Italy"},
                }
            ],
        )
    )
    raw = await tools.geocode_address("Milan")
    data = json.loads(raw)
    assert data["count"] == 1
    assert data["results"][0]["lat"] == pytest.approx(45.4642)
    assert data["results"][0]["address"]["country"] == "Italy"


@pytest.mark.asyncio
@respx.mock
async def test_find_nearby_places_normalises_elements():
    respx.post(settings.OVERPASS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "node",
                        "id": 1,
                        "lat": 45.46,
                        "lon": 9.19,
                        "tags": {
                            "amenity": "restaurant",
                            "name": "Trattoria Milanese",
                            "addr:city": "Milano",
                        },
                    },
                    {
                        "type": "way",
                        "id": 42,
                        "center": {"lat": 45.47, "lon": 9.20},
                        "tags": {"amenity": "restaurant", "name": "Ristorante Duomo"},
                    },
                ]
            },
        )
    )
    raw = await tools.find_nearby_places(45.46, 9.19, 800, "restaurant", 10)
    data = json.loads(raw)
    assert data["count"] == 2
    assert data["places"][0]["name"] == "Trattoria Milanese"
    assert data["places"][1]["id"] == "way/42"


@pytest.mark.asyncio
@respx.mock
async def test_commercial_profile_counts_by_category():
    # Overpass `out count`: un elemento per categoria (5) + uno per il totale.
    respx.post(settings.OVERPASS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "elements": [
                    {"type": "count", "id": 0, "tags": {"total": str(t)}}
                    for t in (10, 3, 5, 1, 2, 18)
                ]
            },
        )
    )
    raw = await tools.commercial_profile(lat=40.798, lon=16.923, radius_m=1500)
    data = json.loads(raw)
    assert data["counts"]["negozi"] == 10
    assert data["counts"]["ristorazione"] == 5
    assert data["totale_commercio"] == 18
    assert "openstreetmap.org" in data["source_url"]
    assert data["scope"]["radius_m"] == 1500


@pytest.mark.asyncio
async def test_commercial_profile_requires_scope():
    raw = await tools.commercial_profile()
    assert "error" in json.loads(raw)


@pytest.mark.asyncio
@respx.mock
async def test_tourism_profile_counts_and_landmarks():
    # 1ª POST = conteggi (5 categorie + totale); 2ª POST = landmark nominati.
    counts_resp = httpx.Response(
        200,
        json={
            "elements": [
                {"type": "count", "id": 0, "tags": {"total": str(t)}}
                for t in (4, 3, 2, 5, 1, 15)  # musei, monumenti, attrazioni, ricettività, cultura, totale
            ]
        },
    )
    landmarks_resp = httpx.Response(
        200,
        json={
            "elements": [
                {"type": "node", "id": 1, "tags": {"name": "Castello di Gioia del Colle", "historic": "castle"}},
                {"type": "node", "id": 2, "tags": {"name": "Museo Archeologico", "tourism": "museum"}},
                {"type": "node", "id": 3, "tags": {"tourism": "attraction"}},  # senza nome → scartato
                {"type": "node", "id": 4, "tags": {"name": "Castello di Gioia del Colle", "historic": "castle"}},  # dup
            ]
        },
    )
    respx.post(settings.OVERPASS_URL).mock(side_effect=[counts_resp, landmarks_resp])
    raw = await tools.tourism_profile(south=40.7, west=16.9, north=40.85, east=17.0)
    data = json.loads(raw)
    assert data["counts"]["musei"] == 4
    assert data["counts"]["ricettivita"] == 5
    assert data["totale_culturale"] == 10  # 15 totale − 5 ricettività
    assert data["totale_ricettivita"] == 5
    names = [m["name"] for m in data["landmarks"]]
    assert "Castello di Gioia del Colle" in names and "Museo Archeologico" in names
    assert len(data["landmarks"]) == 2  # senza-nome scartato + dedup per nome
    assert "openstreetmap.org" in data["source_url"]


@pytest.mark.asyncio
@respx.mock
async def test_get_route_returns_distance_and_steps():
    respx.get(url__regex=rf"{settings.OSRM_URL}/route/v1/.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "distance": 5000,
                        "duration": 600,
                        "geometry": {"type": "LineString", "coordinates": []},
                        "legs": [
                            {
                                "steps": [
                                    {
                                        "distance": 500,
                                        "duration": 60,
                                        "name": "Via Roma",
                                        "maneuver": {
                                            "type": "turn",
                                            "modifier": "left",
                                            "instruction": "Turn left onto Via Roma",
                                        },
                                    }
                                ]
                            }
                        ],
                    }
                ]
            },
        )
    )
    raw = await tools.get_route(45.46, 9.19, 45.48, 9.21)
    data = json.loads(raw)
    assert data["distance_m"] == 5000
    assert data["duration_s"] == 600
    assert data["steps"][0]["name"] == "Via Roma"
