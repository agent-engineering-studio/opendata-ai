"""Deterministic CKAN search safety-net (orchestrator.ckan_fallback).

The Ollama CKAN specialist is unreliable; this guarantees public datasets still
surface for a "find the data" query. Uses a fake CkanClient (no network).
"""

from __future__ import annotations

import pytest

from opendata_backend.orchestrator import ckan_fallback
from opendata_backend.orchestrator.ckan_fallback import (
    ckan_geo_fallback,
    has_geo,
    keywords,
)
from opendata_backend.orchestrator.parsing import Resource


def test_keywords_strips_stopwords_and_wrapper() -> None:
    assert keywords("trovami le piste ciclabili di Bologna") == "piste ciclabili bologna"
    assert (
        keywords("MAP_MODE: bla bla\nUSER QUERY: piste ciclabili Bologna")
        == "piste ciclabili bologna"
    )


def test_has_geo() -> None:
    assert has_geo([Resource(name="x", url="https://a/x.geojson", format="GEOJSON")])
    assert not has_geo([Resource(name="x", url="https://a/x.csv", format="CSV")])


class _FakeCkan:
    def __init__(self, result: dict) -> None:
        self._result = result

    async def __aenter__(self) -> "_FakeCkan":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def action(self, action: str, *, base_url=None, params=None):
        return self._result


@pytest.mark.asyncio
async def test_fallback_keeps_bologna_geo_drops_other_comune(monkeypatch) -> None:
    result = {
        "count": 2,
        "results": [
            {
                "title": "Piste ciclabili",
                "resources": [
                    {
                        "url": "https://dati.emilia-romagna.it/dataset/x/resource/y/download/pisteciclabilirg.kml",
                        "format": "KML",
                    },
                    {
                        "url": "http://dati.cittametropolitana.bo.it/Engine/SIT_PMC_ARCHI.zip",
                        "format": "ZIP",
                    },
                ],
            },
            {
                "title": "Piste ciclabili Genova",
                "resources": [
                    {
                        "url": "https://opendatacomunegenova.s3.amazonaws.com/risorse/piste_ciclabili.geojson",
                        "format": "GEOJSON",
                    }
                ],
            },
        ],
    }
    monkeypatch.setattr(ckan_fallback, "CkanClient", lambda *a, **k: _FakeCkan(result))

    out = await ckan_geo_fallback(
        "trovami le piste ciclabili di Bologna",
        "https://www.dati.gov.it/opendata",
        prefer_geo=True,
    )
    urls = {r.url for r in out}
    assert any("emilia-romagna" in u for u in urls), "regional ER resource kept"
    assert any("cittametropolitana.bo.it" in u for u in urls), "Bologna metro kept"
    assert not any("genova" in u for u in urls), "different comune dropped by geo_filter"
    assert all((r.format or "").upper() in ckan_fallback.GEO_FORMATS for r in out)


@pytest.mark.asyncio
async def test_fallback_returns_empty_on_search_error(monkeypatch) -> None:
    class _Boom:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def action(self, *a, **k):
            raise RuntimeError("ckan down")

    monkeypatch.setattr(ckan_fallback, "CkanClient", lambda *a, **k: _Boom())
    out = await ckan_geo_fallback("piste ciclabili Bologna", None, prefer_geo=True)
    assert out == []
