"""Test degli endpoint binari del Quality Lab (#157): xlsx-to-csv, shapefile-to-geojson."""

from __future__ import annotations

import base64
import csv
import io
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient

from opendata_backend.auth import ClerkUser
from opendata_backend.auth import dependencies as auth_dep
from opendata_backend.config import Settings, get_settings
from opendata_backend.routers import quality


def _client() -> TestClient:
    user = ClerkUser(subject="u_bin", email=None, claims={})

    async def _user() -> ClerkUser:
        return user

    app = FastAPI()
    app.include_router(quality.router)
    app.dependency_overrides[get_settings] = lambda: Settings(auth_enabled=False)  # type: ignore[call-arg]
    app.dependency_overrides[auth_dep.require_user] = _user
    return TestClient(app)


def _b64_xlsx() -> str:
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.append(["nome", "eta"])
    wb.active.append(["Anna", 30])
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def _b64_shapefile_zip(tmp_path) -> str:
    import pyproj
    import shapefile

    stem = str(tmp_path / "d")
    w = shapefile.Writer(stem, shapeType=shapefile.POINT)
    w.field("name", "C")
    w.point(12.4924, 41.8902)
    w.record("Roma")
    w.close()
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as zf:
        for ext in (".shp", ".dbf", ".shx"):
            with open(stem + ext, "rb") as fh:
                zf.writestr("d" + ext, fh.read())
        zf.writestr("d.prj", pyproj.CRS.from_epsg(4326).to_wkt())
    return base64.b64encode(z.getvalue()).decode()


def test_xlsx_to_csv_endpoint() -> None:
    res = _client().post("/quality/xlsx-to-csv", json={"content_base64": _b64_xlsx()})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    rows = list(csv.reader(io.StringIO(body["content"])))
    assert rows[0] == ["nome", "eta"] and rows[1] == ["Anna", "30"]


def test_shapefile_to_geojson_endpoint(tmp_path) -> None:
    res = _client().post(
        "/quality/shapefile-to-geojson", json={"content_base64": _b64_shapefile_zip(tmp_path)}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["feature_count"] == 1
    assert body["geojson"]["features"][0]["properties"]["name"] == "Roma"


def test_binary_endpoints_require_input() -> None:
    client = _client()
    assert client.post("/quality/xlsx-to-csv", json={}).status_code == 400
    assert client.post("/quality/shapefile-to-geojson", json={}).status_code == 400


def test_xlsx_invalid_base64() -> None:
    res = _client().post("/quality/xlsx-to-csv", json={"content_base64": "!!!notb64!!!"})
    assert res.status_code == 400


def test_xlsx_legacy_xls_is_422() -> None:
    # bytes non-XLSX validi base64 → openpyxl non li legge → 422 (non 500/501).
    res = _client().post(
        "/quality/xlsx-to-csv",
        json={"content_base64": base64.b64encode(b"\xd0\xcf\x11\xe0legacy xls").decode()},
    )
    assert res.status_code == 422


def test_shapefile_zip_bomb_413(tmp_path, monkeypatch) -> None:
    from opendata_core.quality import shapefile as shp_mod

    monkeypatch.setattr(shp_mod, "MAX_UNCOMPRESSED", 10)
    res = _client().post(
        "/quality/shapefile-to-geojson", json={"content_base64": _b64_shapefile_zip(tmp_path)}
    )
    assert res.status_code == 413
