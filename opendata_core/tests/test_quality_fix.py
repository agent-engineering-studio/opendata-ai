"""Test dell'auto-fix CSV (Data Quality Lab #49)."""

from __future__ import annotations

import csv
import io

from opendata_core.quality import fix_csv


def _codes(rep: dict) -> set[str]:
    return {c["codice"] for c in rep["changes"]}


def _parse(content: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content)))


def test_normalizza_separatore_e_decimali_e_date() -> None:
    csv_in = (
        "comune;valore;data\n"
        "Bari;1.234,56;01/02/2023\n"
        "Gioia del Colle;12,3;2023-03-04\n"
    )
    out = fix_csv(csv_in)
    rows = _parse(out["content"])
    assert rows[0] == ["comune", "valore", "data"]
    assert rows[1] == ["Bari", "1234.56", "2023-02-01"]   # decimale IT→punto, data gg/mm→ISO
    assert rows[2] == ["Gioia del Colle", "12.3", "2023-03-04"]
    codes = _codes(out)
    assert {"separatore", "decimali", "date_iso"} <= codes


def test_trim_spazi_e_bom() -> None:
    out = fix_csv("﻿a,b\n  x  ,1\n y ,2\n")
    rows = _parse(out["content"])
    assert rows[1] == ["x", "1"]
    assert rows[2] == ["y", "2"]
    assert {"bom", "spazi"} <= _codes(out)


def test_header_vuoti_e_duplicati() -> None:
    out = fix_csv("a,,a\n1,2,3\n")
    assert "header" in _codes(out)
    header = _parse(out["content"])[0]
    assert header[0] == "a"
    assert header[1] == "colonna_2"   # vuoto → nome generato
    assert header[2] == "a_2"         # duplicato → suffisso


def test_clean_csv_minime_modifiche() -> None:
    # già pulito + comma → nessuna modifica strutturale
    out = fix_csv("comune,popolazione\nBari,320475\nModugno,38500\n")
    assert out["changes"] == []
    assert _parse(out["content"])[1] == ["Bari", "320475"]


def test_non_tocca_migliaia_ambigue() -> None:
    # "1.234" senza virgola è ambiguo (migliaia vs decimale) → NON modificato
    out = fix_csv("id,n\n1,1.234\n2,5.678\n")
    rows = _parse(out["content"])
    assert rows[1] == ["1", "1.234"]
    assert "decimali" not in _codes(out)


def test_data_non_valida_lasciata() -> None:
    # 31/13/2023 (mese 13) non è valida → lasciata invariata
    out = fix_csv("evento,quando\na,31/13/2023\nb,01/02/2023\n")
    rows = _parse(out["content"])
    assert rows[1][1] == "31/13/2023"
    assert rows[2][1] == "2023-02-01"
