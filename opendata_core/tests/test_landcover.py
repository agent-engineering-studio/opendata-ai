"""Test del connettore copertura del suolo ISPRA (WMS GetFeatureInfo, #128 Fase 2c)."""

from __future__ import annotations

import httpx

from opendata_core.ispra import LandCoverClient, LandCoverInfo
from opendata_core.ispra.landcover import _parse_clc


def test_parse_clc_artificiale() -> None:
    # codice CLC 1xx = superfici artificiali → impermeabilizzato
    info = _parse_clc({"features": [{"properties": {"clc18": "111"}}]}, "http://x")
    assert isinstance(info, LandCoverInfo)
    assert info.clc_code == "111" and info.macroclasse == 1
    assert info.impermeabilizzato is True
    assert "artificiali" in info.descrizione.lower()
    assert info.licenza.startswith("ISPRA")


def test_parse_clc_non_artificiale() -> None:
    info = _parse_clc({"features": [{"properties": {"clc18": "311"}}]}, "u")
    assert info is not None
    assert info.macroclasse == 3 and info.impermeabilizzato is False


def test_parse_clc_senza_feature_o_codice() -> None:
    assert _parse_clc({"features": []}, "u") is None
    assert _parse_clc({"features": [{"properties": {}}]}, "u") is None
    assert _parse_clc({"features": [{"properties": {"clc18": "n/a"}}]}, "u") is None


def test_params_bbox_wms_130_axis_lat_lon() -> None:
    c = LandCoverClient()
    p = c._params(41.9028, 12.4964)
    assert p["request"] == "GetFeatureInfo" and p["version"] == "1.3.0"
    assert p["crs"] == "EPSG:4258" and p["info_format"] == "application/json"
    # bbox in ordine lat,lon (min prima) per CRS geografico in WMS 1.3.0
    miny, minx, maxy, maxx = (float(x) for x in p["bbox"].split(","))
    assert miny < 41.9028 < maxy and minx < 12.4964 < maxx


async def test_land_cover_at_failsafe_on_http_error(monkeypatch) -> None:
    """Errore di trasporto → None (fail-safe), mai eccezione."""
    async def _boom(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise httpx.ConnectError("down")

    async with LandCoverClient() as c:
        monkeypatch.setattr(c._client, "get", _boom)
        assert await c.land_cover_at(41.9, 12.5) is None


async def test_land_cover_at_parses_live_shape(monkeypatch) -> None:
    """Forma reale della risposta (verificata live) → LandCoverInfo corretto."""
    class _Resp:
        request = httpx.Request("GET", "https://sdi.isprambiente.it/geoserver/lc/wms")

        def raise_for_status(self) -> None:  # noqa: D401
            return None

        def json(self) -> dict:
            return {"features": [{"properties": {"objectid_1": 1, "clc18": "111"}}]}

    async def _get(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        return _Resp()

    async with LandCoverClient() as c:
        monkeypatch.setattr(c._client, "get", _get)
        info = await c.land_cover_at(41.9028, 12.4964)
    assert info is not None and info.impermeabilizzato is True and info.clc_code == "111"
