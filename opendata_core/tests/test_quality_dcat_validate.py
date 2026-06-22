"""Test del validatore DCAT-AP_IT + FAIR check (Data Quality Lab / Punto 04 #52)."""

from __future__ import annotations

from opendata_core.quality import generate_dcat, profile_csv, validate_dcat

_CSV = "comune,popolazione,anno\nBari,320475,2023\nLecce,95000,2023\n"


def test_scheda_completa_valida_fair_alto() -> None:
    meta = generate_dcat(
        profile_csv(_CSV), titolo="Popolazione residente",
        descrizione="Popolazione per comune.", licenza="CC-BY-4.0",
        ente="Regione Puglia", tema="SOCI", frequenza="ANNUAL",
        url="https://dati.puglia.it/pop.csv",
    )
    v = validate_dcat(meta)
    assert v["valido"] is True
    assert v["findings"] == [] or all(f["livello"] != "alto" for f in v["findings"])
    assert v["licenza"]["aperta"] is True
    assert v["licenza"]["suggerita"] is None
    # CSV + licenza aperta + tutti i campi → FAIR alto
    assert v["fair"]["overall"] >= 85
    assert v["fair"]["interoperable"] >= 80  # CSV aperto + schema + @type


def test_scheda_incompleta_segnala_obbligatori() -> None:
    meta = generate_dcat(profile_csv(_CSV))  # nessun campo editoriale
    v = validate_dcat(meta)
    assert v["valido"] is False
    codici = {f["codice"] for f in v["findings"]}
    assert "title" in codici and "description" in codici
    assert "license_missing" in codici
    assert v["licenza"]["aperta"] is None
    assert v["licenza"]["suggerita"] == "CC-BY-4.0"


def test_licenza_non_aperta_segnalata() -> None:
    meta = generate_dcat(
        profile_csv(_CSV), titolo="X", descrizione="Y", ente="Z",
        tema="GOVE", frequenza="ANNUAL", licenza="CC-BY-NC-4.0",
        url="https://x.it/d.csv",
    )
    v = validate_dcat(meta)
    assert v["licenza"]["aperta"] is False
    assert any(f["codice"] == "license_closed" for f in v["findings"])
    assert v["valido"] is False  # licenza non aperta è "alto"
    assert v["fair"]["reusable"] == 50  # publisher+freq+desc ma NESSUN credito licenza (−50)


def test_formato_chiuso_penalizza_interoperabilita() -> None:
    meta = generate_dcat(
        profile_csv(_CSV), titolo="X", descrizione="Y", ente="Z",
        tema="GOVE", frequenza="ANNUAL", licenza="CC-BY-4.0",
        url="https://x.it/d.pdf",
    )
    # forza il formato a PDF nella distribuzione
    meta["dataset"]["dcat:distribution"][0]["dct:format"] = "PDF"
    v = validate_dcat(meta)
    assert any(f["codice"] == "format_closed" for f in v["findings"])
    assert v["fair"]["interoperable"] < 60  # niente credito formato aperto


def test_accetta_anche_il_dataset_diretto() -> None:
    # senza wrapper: passa direttamente il dict "dataset"
    meta = generate_dcat(profile_csv(_CSV), titolo="X", descrizione="Y",
                         licenza="CC-BY-4.0", ente="Z", tema="GOVE", frequenza="ANNUAL",
                         url="https://x.it/d.csv")
    v = validate_dcat(meta["dataset"])
    assert v["licenza"]["aperta"] is True
