"""Test dell'endpoint /quality/profile (Data Quality Lab)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from opendata_backend.auth import ClerkUser
from opendata_backend.auth import dependencies as auth_dep
from opendata_backend.config import Settings, get_settings
from opendata_backend.routers import quality


def _client() -> TestClient:
    user = ClerkUser(subject="u_quality", email=None, claims={})

    async def _user() -> ClerkUser:
        return user

    app = FastAPI()
    app.include_router(quality.router)
    app.dependency_overrides[get_settings] = lambda: Settings(auth_enabled=False)  # type: ignore[call-arg]
    app.dependency_overrides[auth_dep.require_user] = _user
    return TestClient(app)


def test_profile_content_ok() -> None:
    client = _client()
    res = client.post(
        "/quality/profile",
        json={"content": "comune,popolazione\nGioia del Colle,27889\nBari,320475\n"},
    )
    assert res.status_code == 200
    rep = res.json()
    assert rep["format"] == "CSV"
    assert rep["colonne"] == 2
    assert rep["righe"] == 2
    assert "punteggio" in rep
    assert any(c["nome"] == "popolazione" and c["tipo"] == "intero" for c in rep["colonne_profilo"])


def test_profile_requires_input() -> None:
    res = _client().post("/quality/profile", json={})
    assert res.status_code == 400


def test_profile_unsupported_format() -> None:
    res = _client().post("/quality/profile", json={"content": "x", "format": "xlsx"})
    assert res.status_code == 415


def test_fix_content_ok() -> None:
    client = _client()
    res = client.post("/quality/fix", json={"content": "a;b\n1.234,5;01/02/2023\n"})
    assert res.status_code == 200
    rep = res.json()
    assert "content" in rep and "changes" in rep
    assert "1234.5" in rep["content"]      # decimale IT → punto
    assert "2023-02-01" in rep["content"]  # data gg/mm → ISO


def test_fix_requires_input() -> None:
    assert _client().post("/quality/fix", json={}).status_code == 400


def test_profile_dispatches_geojson() -> None:
    gj = (
        '{"type":"FeatureCollection","features":'
        '[{"type":"Feature","geometry":{"type":"Point","coordinates":[11.37,44.49]},"properties":{}}]}'
    )
    res = _client().post("/quality/profile", json={"content": gj})
    assert res.status_code == 200
    rep = res.json()
    assert rep["format"] == "GEOJSON"
    assert rep["crs_wgs84"] is True
    assert rep["features"] == 1


def test_profile_geojson_projected_flagged() -> None:
    gj = (
        '{"type":"FeatureCollection","features":'
        '[{"type":"Feature","geometry":{"type":"Point","coordinates":[612345.0,4912345.0]},"properties":{}}]}'
    )
    rep = _client().post("/quality/profile", json={"content": gj}).json()
    assert rep["crs_wgs84"] is False
    assert any(f["codice"] == "coord_proiettate" for f in rep["findings"])


def test_fix_geojson_rejected() -> None:
    gj = '{"type":"FeatureCollection","features":[]}'
    res = _client().post("/quality/fix", json={"content": gj, "format": "geojson"})
    assert res.status_code == 415


def test_metadata_csv_dcat() -> None:
    res = _client().post("/quality/metadata", json={
        "content": "comune,popolazione\nBari,320475\n",
        "titolo": "Popolazione residente", "licenza": "CC-BY-4.0",
    })
    assert res.status_code == 200
    d = res.json()
    assert d["profilo"] == "DCAT-AP_IT"
    assert d["dataset"]["dct:title"] == "Popolazione residente"
    assert d["dataset"]["dcat:distribution"][0]["dct:format"] == "CSV"
    assert any(c["nome"] == "popolazione" for c in d["schema_campi"])


def test_metadata_requires_input() -> None:
    assert _client().post("/quality/metadata", json={}).status_code == 400


def test_schema_csv_ddl() -> None:
    res = _client().post("/quality/schema", json={
        "content": "codice,comune,popolazione\n1,Bari,320475\n2,Monopoli,49000\n",
        "table_name": "Comuni",
    })
    assert res.status_code == 200
    s = res.json()
    assert s["table_name"] == "comuni"
    assert s["primary_key"] == "codice"  # univoco, senza vuoti, id-like
    assert "CREATE TABLE comuni (" in s["ddl"]
    types = {c["name"]: c["sql_type"] for c in s["columns"]}
    assert types["popolazione"] == "INTEGER"


def test_schema_geojson_rejected() -> None:
    gj = '{"type":"FeatureCollection","features":[]}'
    res = _client().post("/quality/schema", json={"content": gj, "format": "geojson"})
    assert res.status_code == 415


def test_schema_requires_input() -> None:
    assert _client().post("/quality/schema", json={}).status_code == 400


def test_to_geojson_csv_ok() -> None:
    res = _client().post("/quality/to-geojson", json={
        "content": "nome;lat;lon\nBari;41,12;16,87\n",
    })
    assert res.status_code == 200
    r = res.json()
    assert r["ok"] is True and r["n_features"] == 1
    assert r["geojson"]["features"][0]["geometry"]["coordinates"] == [16.87, 41.12]


def test_to_geojson_no_coords_reports_candidates() -> None:
    r = _client().post("/quality/to-geojson", json={"content": "a,b\n1,2\n"}).json()
    assert r["ok"] is False
    assert r["candidate_columns"] == ["a", "b"]


def test_to_geojson_json_array() -> None:
    res = _client().post("/quality/to-geojson", json={
        "content": '[{"nome":"Bari","y":41.1,"x":16.8}]', "format": "json",
    })
    assert res.status_code == 200
    assert res.json()["n_features"] == 1


def test_summary_csv_ok() -> None:
    res = _client().post("/quality/summary", json={
        "content": "provincia;popolazione;anno\nBA;320000;2021\nLE;95000;2022\n",
    })
    assert res.status_code == 200
    s = res.json()
    assert s["righe"] == 2
    assert any(n["column"] == "popolazione" for n in s["numeric"])
    assert any(t["column"] == "anno" for t in s["serie_temporali"])


def test_summary_geojson_rejected() -> None:
    gj = '{"type":"FeatureCollection","features":[]}'
    assert _client().post("/quality/summary", json={"content": gj, "format": "geojson"}).status_code == 415
