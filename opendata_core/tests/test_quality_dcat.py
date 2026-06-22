"""Test del generatore di metadati DCAT-AP_IT (Data Quality Lab #49)."""

from __future__ import annotations

from opendata_core.quality import generate_dcat, profile_csv, profile_geojson


def test_dcat_da_csv_deriva_formato_schema_keyword() -> None:
    prof = profile_csv("comune,popolazione_residente,data_rilevazione\nBari,320475,2023-01-01\n")
    d = generate_dcat(prof, url="https://dati.example.it/x.csv")

    assert d["profilo"] == "DCAT-AP_IT"
    dist = d["dataset"]["dcat:distribution"][0]
    assert dist["dct:format"] == "CSV"
    assert dist["dcat:mediaType"] == "text/csv"
    assert dist["dcat:downloadURL"] == "https://dati.example.it/x.csv"
    # schema dei campi con tipi XSD dedotti dal profilo
    schema = {c["nome"]: c["tipo_xsd"] for c in d["schema_campi"]}
    assert schema["popolazione_residente"] == "xsd:integer"
    assert schema["data_rilevazione"] == "xsd:date"
    assert schema["comune"] == "xsd:string"
    # keyword dai nomi colonna (stopword come "data"/"cod" escluse)
    assert "popolazione" in d["dataset"]["dcat:keyword"]


def test_dcat_campi_mancanti_quando_non_forniti() -> None:
    prof = profile_csv("a,b\n1,2\n")
    d = generate_dcat(prof)
    assert d["dataset"]["dct:title"] == "<da compilare>"
    codici = " ".join(d["campi_mancanti"])
    assert "titolo" in codici and "descrizione" in codici and "licenza" in codici


def test_dcat_campi_forniti_riempiti() -> None:
    prof = profile_csv("a,b\n1,2\n")
    d = generate_dcat(
        prof,
        titolo="Popolazione residente",
        descrizione="Residenti per comune",
        licenza="CC-BY-4.0",
        ente="Comune di Bari",
        tema="GOVE",
        frequenza="ANNUAL",
    )
    ds = d["dataset"]
    assert ds["dct:title"] == "Popolazione residente"
    assert ds["dct:license"] == "CC-BY-4.0"
    assert ds["dct:publisher"]["foaf:name"] == "Comune di Bari"
    assert ds["dcat:theme"] == "GOVE"
    assert d["campi_mancanti"] == []


def test_dcat_da_geojson() -> None:
    gj = '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[11.3,44.5]},"properties":{}}]}'
    prof = profile_geojson(gj)
    d = generate_dcat(prof)
    dist = d["dataset"]["dcat:distribution"][0]
    assert dist["dct:format"] == "GEOJSON"
    assert dist["dcat:mediaType"] == "application/geo+json"
    assert d["schema_campi"] == []  # i geo non hanno profilo colonne tabellare
