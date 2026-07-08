"""Test della skill A2A `data_quality` (logica pura) + AgentCard (Punto 05 #53)."""

from __future__ import annotations

from opendata_backend.a2a.agent_card import SKILL_QUALITY, build_agent_card
from opendata_backend.a2a.quality_skill import AZIONI, run_quality_skill

_CSV = "comune,popolazione,anno\nBari,320475,2023\nLecce,95000,2023\n"


def test_profile_default() -> None:
    r = run_quality_skill({"content": _CSV})
    assert r["ok"] is True and r["azione"] == "profile"
    assert r["result"]["format"] == "CSV"
    assert r["result"]["righe"] == 2


def test_schema_summary_scale() -> None:
    assert "CREATE TABLE" in run_quality_skill({"azione": "schema", "content": _CSV})["result"]["ddl"]
    s = run_quality_skill({"azione": "summary", "content": _CSV})["result"]
    assert any(n["column"] == "popolazione" for n in s["numeric"])
    sc = run_quality_skill({"azione": "scale", "content": _CSV})["result"]
    assert sc["dimensione"]["classe"] == "piccolo"


def test_validate_returns_fair() -> None:
    r = run_quality_skill({"azione": "validate", "content": _CSV, "licenza": "CC-BY-4.0",
                           "titolo": "Pop", "descrizione": "x", "ente": "Regione Puglia",
                           "tema": "SOCI", "frequenza": "ANNUAL", "url": "https://x.it/p.csv"})
    assert r["ok"] is True
    assert r["result"]["validazione"]["licenza"]["aperta"] is True
    assert "fair" in r["result"]["validazione"]


def test_to_geojson() -> None:
    r = run_quality_skill({"azione": "to-geojson", "content": "nome;lat;lon\nBari;41,12;16,87\n"})
    assert r["result"]["n_features"] == 1


def test_hvd_stima_con_confidenza() -> None:
    r = run_quality_skill({"azione": "hvd", "content": "fermate,orari\nPiazza Moro,07:30\n"})
    assert r["ok"] is True
    top = r["result"]["categorie"][0]
    assert top["codice"] == "mobility" and top["confidenza"] == "media"
    assert "nota" in r["result"]


def test_to_parquet_base64() -> None:
    import base64
    import io

    import pytest

    pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    r = run_quality_skill({"azione": "to-parquet", "content": _CSV})
    assert r["ok"] is True and r["result"]["ok"] is True
    assert r["result"]["content_encoding"] == "base64"
    table = pq.read_table(io.BytesIO(base64.b64decode(r["result"]["content"])))
    assert table.column("popolazione").to_pylist() == [320475, 95000]


def test_to_parquet_rejects_geojson() -> None:
    gj = '{"type":"FeatureCollection","features":[]}'
    r = run_quality_skill({"azione": "to-parquet", "content": gj, "format": "geojson"})
    assert r["ok"] is False and "CSV" in r["error"]


def test_package_returns_files() -> None:
    r = run_quality_skill({"azione": "package", "content": _CSV, "licenza": "CC-BY-4.0",
                           "titolo": "Pop", "ente": "Regione Puglia"})
    assert r["ok"] is True and r["azione"] == "package"
    files = r["result"]["files"]
    assert set(files) == {"dati.csv", "metadati-dcat-ap_it.jsonld", "LICENSE.txt", "README.txt"}
    assert "Creative Commons" in files["LICENSE.txt"]


def test_enrich_suggests_istat_join() -> None:
    r = run_quality_skill({"azione": "enrich", "content": _CSV})
    assert r["ok"] is True and r["azione"] == "enrich"
    codici = {a["codice"] for a in r["result"]["arricchimenti"]}
    assert "join_istat" in codici


def test_enrich_rejects_geojson() -> None:
    gj = '{"type":"FeatureCollection","features":[]}'
    r = run_quality_skill({"azione": "enrich", "content": gj, "format": "geojson"})
    assert r["ok"] is False and "CSV" in r["error"]


def test_normalize_generates_lookup_and_views() -> None:
    csv_ripetuto = "id,zona\n" + "".join(f"{i},{'Nord' if i % 2 == 0 else 'Sud'}\n" for i in range(20))
    r = run_quality_skill({"azione": "normalize", "content": csv_ripetuto})
    assert r["ok"] is True and r["azione"] == "normalize"
    assert any(t["colonna_originale"] == "zona" for t in r["result"]["tabelle_lookup"])


def test_normalize_rejects_geojson() -> None:
    gj = '{"type":"FeatureCollection","features":[]}'
    r = run_quality_skill({"azione": "normalize", "content": gj, "format": "geojson"})
    assert r["ok"] is False and "CSV" in r["error"]


def test_geo_schema_generates_postgis_ddl() -> None:
    gj = (
        '{"type":"FeatureCollection","features":'
        '[{"type":"Feature","geometry":{"type":"Point","coordinates":[11.37,44.49]},"properties":{}}]}'
    )
    r = run_quality_skill({"azione": "geo-schema", "content": gj})
    assert r["ok"] is True and r["azione"] == "geo-schema"
    assert "CREATE TABLE" in r["result"]["ddl_postgis"]


def test_geo_schema_rejects_csv() -> None:
    r = run_quality_skill({"azione": "geo-schema", "content": _CSV})
    assert r["ok"] is False and "GeoJSON" in r["error"]


def test_metadata_schema_org() -> None:
    r = run_quality_skill({"azione": "metadata-schema-org", "content": _CSV, "titolo": "Pop"})
    assert r["ok"] is True and r["azione"] == "metadata-schema-org"
    assert r["result"]["profilo"] == "schema.org/Dataset"
    assert r["result"]["dataset"]["name"] == "Pop"


def test_validate_schema_org_via_vocabolario() -> None:
    r = run_quality_skill({"azione": "validate", "content": _CSV, "vocabolario": "schema_org",
                           "titolo": "Pop", "descrizione": "x", "licenza": "CC-BY-4.0",
                           "ente": "Regione Puglia", "tema": "SOCI", "frequenza": "ANNUAL"})
    assert r["ok"] is True
    assert r["result"]["metadata"]["profilo"] == "schema.org/Dataset"
    assert r["result"]["validazione"]["valido"] is True


def test_fix_rejects_geojson() -> None:
    gj = '{"type":"FeatureCollection","features":[]}'
    r = run_quality_skill({"azione": "fix", "content": gj, "format": "geojson"})
    assert r["ok"] is False and "CSV" in r["error"]


def test_missing_content_and_unknown_action() -> None:
    assert run_quality_skill({})["ok"] is False
    bad = run_quality_skill({"azione": "boh", "content": _CSV})
    assert bad["ok"] is False and "azioni" in bad


def test_agent_card_publishes_quality_skill() -> None:
    card = build_agent_card("http://localhost:8000")
    ids = {s.id for s in card.skills}
    assert SKILL_QUALITY in ids
    assert set(AZIONI) >= {
        "profile", "fix", "schema", "normalize", "summary", "scale", "enrich", "hvd",
        "geo-schema", "to-geojson", "to-parquet", "validate", "metadata-schema-org",
    }
