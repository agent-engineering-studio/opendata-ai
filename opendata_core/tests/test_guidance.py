"""Test della guida operativa open-data (comuni senza/con pochi dati)."""

from __future__ import annotations

from opendata_core.maturity import build_guida_opendata


def test_guida_zero_datasets() -> None:
    g = build_guida_opendata("Comune di Test", n_datasets=0, total_on_portal=0)
    assert "Comune di Test" in g["titolo"]
    assert "Non sono stati trovati" in g["premessa"]
    assert len(g["passi"]) >= 5
    assert all("titolo" in p and "descrizione" in p for p in g["passi"])
    assert any("dati.gov.it" in r["url"] for r in g["riferimenti"])
    assert "nota" in g  # disclaimer "non è un giudizio"


def test_guida_few_datasets_mentions_count() -> None:
    g = build_guida_opendata("Comune X", n_datasets=2, total_on_portal=2)
    assert "2 dataset" in g["premessa"]


def test_guida_low_open_license_adds_warning() -> None:
    g = build_guida_opendata("Comune Y", n_datasets=4, total_on_portal=4, open_license_ratio=0.25)
    assert any("licenz" in p["titolo"].lower() for p in g["passi"])
