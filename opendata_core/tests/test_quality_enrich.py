"""Test dei suggerimenti di arricchimento (Data Quality Lab #49, ultima voce)."""

from __future__ import annotations

from opendata_core.quality import advise_enrichment, profile_csv


def test_comune_senza_codice_istat_suggerisce_join() -> None:
    p = profile_csv("comune,popolazione\nGioia del Colle,27889\nBari,320475\nModugno,40371\n")
    e = advise_enrichment(p)
    codici = {a["codice"] for a in e["arricchimenti"]}
    assert "join_istat" in codici
    join = next(a for a in e["arricchimenti"] if a["codice"] == "join_istat")
    assert "comune" in join["colonne"]


def test_comune_gia_codificato_non_suggerisce_join() -> None:
    p = profile_csv("comune,codice_istat\nBari,072006\nModugno,072024\n")
    e = advise_enrichment(p)
    codici = {a["codice"] for a in e["arricchimenti"]}
    assert "join_istat" not in codici


def test_indirizzo_senza_coordinate_suggerisce_geocoding() -> None:
    p = profile_csv("indirizzo,civico\nVia Roma,12\nVia Garibaldi,3\n")
    e = advise_enrichment(p)
    codici = {a["codice"] for a in e["arricchimenti"]}
    assert "geocoding" in codici


def test_indirizzo_con_coordinate_non_suggerisce_geocoding() -> None:
    p = profile_csv(
        "indirizzo,lat,lon\nVia Roma,41.12,16.87\nVia Garibaldi,41.13,16.88\n"
    )
    e = advise_enrichment(p)
    codici = {a["codice"] for a in e["arricchimenti"]}
    assert "geocoding" not in codici


def test_colonna_categoriale_a_bassa_cardinalita_suggerisce_vocabolario() -> None:
    righe = "".join(f"{i},{'Nord' if i % 2 == 0 else 'Sud'}\n" for i in range(20))
    p = profile_csv("id,zona\n" + righe)
    e = advise_enrichment(p)
    codici = {a["codice"] for a in e["arricchimenti"]}
    assert "vocabolario_controllato" in codici
    vocab = next(a for a in e["arricchimenti"] if a["codice"] == "vocabolario_controllato")
    assert "zona" in vocab["colonne"]


def test_colonna_alta_cardinalita_non_suggerisce_vocabolario() -> None:
    righe = "".join(f"{i},testo unico numero {i}\n" for i in range(50))
    p = profile_csv("id,descrizione\n" + righe)
    e = advise_enrichment(p)
    codici = {a["codice"] for a in e["arricchimenti"]}
    assert "vocabolario_controllato" not in codici


def test_dataset_pulito_senza_suggerimenti() -> None:
    p = profile_csv("id,valore\n1,10\n2,20\n3,30\n")
    e = advise_enrichment(p)
    assert e["arricchimenti"] == []
