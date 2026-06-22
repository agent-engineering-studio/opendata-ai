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


def test_package_returns_files() -> None:
    r = run_quality_skill({"azione": "package", "content": _CSV, "licenza": "CC-BY-4.0",
                           "titolo": "Pop", "ente": "Regione Puglia"})
    assert r["ok"] is True and r["azione"] == "package"
    files = r["result"]["files"]
    assert set(files) == {"dati.csv", "metadati-dcat-ap_it.jsonld", "LICENSE.txt", "README.txt"}
    assert "Creative Commons" in files["LICENSE.txt"]


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
    assert set(AZIONI) >= {"profile", "fix", "schema", "summary", "scale", "to-geojson", "validate"}
