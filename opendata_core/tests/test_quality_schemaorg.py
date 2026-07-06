"""Test dei metadati schema.org/Dataset — generazione (Data Quality Lab #52)."""

from __future__ import annotations

from opendata_core.quality import generate_schema_org, profile_csv

_PROFILE = profile_csv("comune,popolazione\nBari,320475\nLecce,95000\n")


def test_placeholder_quando_campi_editoriali_assenti() -> None:
    r = generate_schema_org(_PROFILE)
    assert r["profilo"] == "schema.org/Dataset"
    ds = r["dataset"]
    assert ds["@type"] == "Dataset"
    assert ds["name"] == "<da compilare>"
    assert "nome (name)" in r["campi_mancanti"]
    assert "licenza (license) — suggerita CC-BY-4.0" in r["campi_mancanti"]


def test_campi_editoriali_compilati() -> None:
    r = generate_schema_org(
        _PROFILE, titolo="Popolazione", descrizione="Per comune", licenza="CC-BY-4.0",
        ente="Regione Puglia", tema="SOCI", frequenza="ANNUAL", url="https://x.it/p.csv",
    )
    ds = r["dataset"]
    assert ds["name"] == "Popolazione"
    assert ds["license"] == "CC-BY-4.0"
    assert ds["creator"]["name"] == "Regione Puglia"
    assert ds["distribution"][0]["contentUrl"] == "https://x.it/p.csv"
    assert r["campi_mancanti"] == []


def test_variable_measured_e_schema_campi_dal_profilo() -> None:
    r = generate_schema_org(_PROFILE)
    assert "popolazione" in r["dataset"]["variableMeasured"]
    tipi = {c["nome"]: c["tipo_xsd"] for c in r["schema_campi"]}
    assert tipi["popolazione"] == "xsd:integer"


def test_encoding_format_da_formato_file() -> None:
    r = generate_schema_org(_PROFILE)
    assert r["dataset"]["distribution"][0]["encodingFormat"] == "text/csv"
