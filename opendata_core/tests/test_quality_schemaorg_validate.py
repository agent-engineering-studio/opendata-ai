"""Test del validatore schema.org/Dataset + FAIR (Data Quality Lab #52)."""

from __future__ import annotations

from opendata_core.quality import generate_schema_org, profile_csv, validate_schema_org

_PROFILE = profile_csv("comune,popolazione\nBari,320475\nLecce,95000\n")


def test_scheda_incompleta_non_valida() -> None:
    meta = generate_schema_org(_PROFILE)
    v = validate_schema_org(meta)
    assert v["valido"] is False
    assert v["licenza"]["aperta"] is None
    assert v["licenza"]["suggerita"] == "CC-BY-4.0"
    codici = {f["codice"] for f in v["findings"]}
    assert "name" in codici and "license_missing" in codici


def test_scheda_completa_valida_con_fair_alto() -> None:
    meta = generate_schema_org(
        _PROFILE, titolo="Popolazione", descrizione="Per comune", licenza="CC-BY-4.0",
        ente="Regione Puglia", tema="SOCI", frequenza="ANNUAL", url="https://x.it/p.csv",
    )
    v = validate_schema_org(meta)
    assert v["valido"] is True
    assert v["licenza"]["aperta"] is True
    assert v["fair"]["overall"] >= 85


def test_licenza_non_aperta_segnalata() -> None:
    meta = generate_schema_org(_PROFILE, titolo="X", descrizione="Y", licenza="CC-BY-NC-4.0")
    v = validate_schema_org(meta)
    assert v["licenza"]["aperta"] is False
    assert any(f["codice"] == "license_closed" for f in v["findings"])
