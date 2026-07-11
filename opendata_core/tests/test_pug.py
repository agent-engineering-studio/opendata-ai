"""Test del connettore PUG/PRG open data (#129, Fase 3)."""

from __future__ import annotations

import json

from opendata_core.pug import PugZoning, fetch_zoning, zone_at
from opendata_core.pug.client import _detect_zone_key, _is_zoning_package

# Quadrato ~[16.8..17.0] x [40.7..40.9], proprietà zona "D" (produttiva).
_FC = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "properties": {"zona": "D", "nome": "PIP"},
        "geometry": {"type": "Polygon", "coordinates": [[
            [16.8, 40.7], [17.0, 40.7], [17.0, 40.9], [16.8, 40.9], [16.8, 40.7],
        ]]},
    }],
}


class _FakeCkan:
    def __init__(self, packages: list[dict], content: str) -> None:
        self._packages = packages
        self._content = content

    async def action(self, _action, *, base_url=None, params=None, json_body=None):  # noqa: ANN001, ANN002, ANN003, ANN201
        return {"results": self._packages}

    async def download_resource(self, _url, max_bytes=None):  # noqa: ANN001, ANN201
        return {"content": self._content}


def _pkg(**over) -> dict:  # noqa: ANN003
    base = {
        "title": "Zonizzazione PUG Gioia del Colle",
        "notes": "zone omogenee del piano urbanistico",
        "organization": {"title": "Comune di Gioia del Colle"},
        "resources": [{"format": "GeoJSON", "url": "https://x.it/zoning.geojson"}],
    }
    base.update(over)
    return base


def test_is_zoning_package() -> None:
    assert _is_zoning_package(_pkg(), "Gioia del Colle")
    assert not _is_zoning_package(_pkg(title="Bilancio 2024", notes="spesa"), "Gioia del Colle")
    # zonizzazione di un altro comune → escluso
    assert not _is_zoning_package(_pkg(), "Bari")


def test_detect_zone_key() -> None:
    assert _detect_zone_key([{"properties": {"ZONA": "D"}}]) == "ZONA"
    assert _detect_zone_key([{"properties": {"zto": "C2"}}]) == "zto"
    assert _detect_zone_key([{"properties": {"pippo": 1}}]) is None
    assert _detect_zone_key([]) is None


async def test_fetch_zoning_trovato() -> None:
    fake = _FakeCkan([_pkg()], json.dumps(_FC))
    z = await fetch_zoning(comune_nome="Gioia del Colle", base_url="https://dati.puglia.it", client=fake)
    assert isinstance(z, PugZoning)
    assert z.zone_key == "zona" and len(z.features) == 1
    assert z.source_url.endswith(".geojson")


async def test_zone_at_dentro_e_fuori() -> None:
    fake = _FakeCkan([_pkg()], json.dumps(_FC))
    z = await fetch_zoning(comune_nome="Gioia del Colle", base_url="https://dati.puglia.it", client=fake)
    assert zone_at(z, 40.8, 16.9) == "D"       # dentro il poligono
    assert zone_at(z, 45.0, 9.0) is None        # fuori


async def test_fetch_zoning_nessun_dataset() -> None:
    fake = _FakeCkan([_pkg(title="Bilancio", notes="", organization={})], json.dumps(_FC))
    assert await fetch_zoning(comune_nome="Gioia del Colle", base_url="https://x", client=fake) is None


async def test_fetch_zoning_senza_risorsa_geojson() -> None:
    fake = _FakeCkan([_pkg(resources=[{"format": "PDF", "url": "https://x/z.pdf"}])], "{}")
    assert await fetch_zoning(comune_nome="Gioia del Colle", base_url="https://x", client=fake) is None


async def test_fetch_zoning_failsafe_su_errore() -> None:
    class _Boom:
        async def action(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
            raise RuntimeError("ckan down")

    assert await fetch_zoning(comune_nome="X", base_url="https://x", client=_Boom()) is None
