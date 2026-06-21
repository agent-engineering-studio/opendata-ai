"""Test del motore di profilazione/diagnosi CSV (Data Quality Lab, Punto 01)."""

from __future__ import annotations

from opendata_core.quality import profile_csv


def _codes(rep: dict) -> set[str]:
    return {f["codice"] for f in rep["findings"]}


def test_clean_csv_high_score() -> None:
    csv = (
        "comune,popolazione,data_rilevazione\n"
        "Gioia del Colle,27889,2023-01-01\n"
        "Bari,320475,2023-01-01\n"
        "Modugno,38500,2023-01-01\n"
    )
    rep = profile_csv(csv)
    assert rep["format"] == "CSV"
    assert rep["righe"] == 3
    assert rep["colonne"] == 3
    assert rep["separatore"] == ","
    assert rep["punteggio"] >= 90
    tipi = {c["nome"]: c["tipo"] for c in rep["colonne_profilo"]}
    assert tipi["popolazione"] == "intero"
    assert tipi["data_rilevazione"] == "data"
    assert tipi["comune"] == "testo"


def test_semicolon_delimiter_detected() -> None:
    rep = profile_csv("a;b;c\n1;2;3\n4;5;6\n")
    assert rep["separatore"] == ";"
    assert rep["colonne"] == 3


def test_missing_values_flagged() -> None:
    csv = "nome,valore\nx,\ny,\nz,3\n"  # 2/3 vuoti nella colonna valore
    rep = profile_csv(csv)
    assert "molti_vuoti" in _codes(rep)
    col = next(c for c in rep["colonne_profilo"] if c["nome"] == "valore")
    assert col["vuoti_pct"] >= 60


def test_mixed_types_flagged() -> None:
    csv = "id,mix\n1,10\n2,20\n3,trenta\n4,quaranta\n5,cinquanta\n"
    rep = profile_csv(csv)
    assert "tipi_misti" in _codes(rep)


def test_mixed_date_formats_flagged() -> None:
    csv = "evento,quando\na,2023-01-01\nb,02/03/2023\nc,2023-05-06\n"
    rep = profile_csv(csv)
    assert "date_miste" in _codes(rep)


def test_generic_headers_and_duplicate_rows() -> None:
    csv = "Column1,Column2\nx,1\nx,1\ny,2\n"  # header generici + 1 riga duplicata
    rep = profile_csv(csv)
    codes = _codes(rep)
    assert "header_non_parlante" in codes
    assert "righe_duplicate" in codes
    assert rep["punteggio"] < 100


def test_empty_column_flagged() -> None:
    csv = "a,vuota,b\n1,,x\n2,,y\n"
    rep = profile_csv(csv)
    assert "colonna_vuota" in _codes(rep)
    col = next(c for c in rep["colonne_profilo"] if c["nome"] == "vuota")
    assert col["tipo"] == "vuoto"


def test_bom_and_encoding_noise() -> None:
    rep_bom = profile_csv("﻿a,b\n1,2\n")
    assert "bom" in _codes(rep_bom)
    rep_enc = profile_csv("a,b\nperch�,2\n")
    assert "encoding" in _codes(rep_enc)


def test_empty_file_scores_zero() -> None:
    rep = profile_csv("   ")
    assert rep["punteggio"] == 0
    assert "vuoto" in _codes(rep)


def test_ragged_rows_flagged() -> None:
    csv = "a,b,c\n1,2,3\n4,5\n6,7,8,9\n"
    rep = profile_csv(csv)
    assert "righe_irregolari" in _codes(rep)
