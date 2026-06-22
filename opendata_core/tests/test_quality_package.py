"""Test del pacchetto di pubblicazione (Data Quality Lab / Punto 04 #52)."""

from __future__ import annotations

import json

from opendata_core.quality import build_publish_package, fix_csv, profile_csv

_CSV = "comune,popolazione,anno\nBari,320475,2023\nLecce,95000,2023\n"


def test_pacchetto_completo_contiene_4_file() -> None:
    fixed = fix_csv(_CSV)["content"]
    pkg = build_publish_package(
        profile_csv(fixed), data_filename="dati.csv", data_content=fixed,
        titolo="Popolazione", descrizione="Per comune.", licenza="CC-BY-4.0",
        ente="Regione Puglia", tema="SOCI", frequenza="ANNUAL",
        url="https://dati.puglia.it/pop.csv",
    )
    files = pkg["files"]
    assert set(files) == {"dati.csv", "metadati-dcat-ap_it.jsonld", "LICENSE.txt", "README.txt"}
    # i metadati sono JSON DCAT-AP_IT validi
    meta = json.loads(files["metadati-dcat-ap_it.jsonld"])
    assert meta["profilo"] == "DCAT-AP_IT"
    # licenza nota → nome esteso + URL nel LICENSE.txt
    assert "Creative Commons Attribuzione 4.0" in files["LICENSE.txt"]
    assert "creativecommons.org" in files["LICENSE.txt"]
    # validazione conforme + README riporta lo stato
    assert pkg["validazione"]["valido"] is True
    assert "Punteggio FAIR" in files["README.txt"]
    assert "OK" in files["README.txt"]


def test_licenza_mancante_mette_avviso_e_suggerimento() -> None:
    pkg = build_publish_package(
        profile_csv(_CSV), data_filename="dati.csv", data_content=_CSV,
        titolo="X", descrizione="Y", ente="Z", tema="GOVE", frequenza="ANNUAL",
    )
    lic = pkg["files"]["LICENSE.txt"]
    assert "NON ANCORA INDICATA" in lic
    assert "CC BY 4.0" in lic
    # la validazione segnala la licenza mancante
    assert pkg["validazione"]["valido"] is False
    assert any(f["codice"] == "license_missing" for f in pkg["validazione"]["findings"])


def test_readme_elenca_cose_da_sistemare() -> None:
    pkg = build_publish_package(profile_csv(_CSV), data_filename="dati.csv", data_content=_CSV)
    readme = pkg["files"]["README.txt"]
    assert "DA SISTEMARE PRIMA DI PUBBLICARE" in readme
    assert "COME PUBBLICARE" in readme
