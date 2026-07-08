"""Test del convertitore CSV → Parquet (Data Quality Lab / Punto #101)."""

from __future__ import annotations

import io
import sys

import pytest

from opendata_core.quality import csv_to_parquet

pyarrow = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq  # noqa: E402


def _read_back(content: bytes):
    return pq.read_table(io.BytesIO(content))


def test_roundtrip_tipi_inferiti() -> None:
    csv = (
        "comune;abitanti;superficie;attivo\n"
        "Bari;320000;117,4;si\n"
        "Gioia del Colle;27000;208,5;no\n"
    )
    r = csv_to_parquet(csv)

    assert r["ok"] is True
    assert r["righe"] == 2 and r["colonne"] == 4
    assert r["schema"] == [
        {"nome": "comune", "tipo": "testo"},
        {"nome": "abitanti", "tipo": "intero"},
        {"nome": "superficie", "tipo": "decimale"},
        {"nome": "attivo", "tipo": "booleano"},
    ]

    table = _read_back(r["content"])
    assert table.column_names == ["comune", "abitanti", "superficie", "attivo"]
    assert table.column("abitanti").to_pylist() == [320000, 27000]
    # la virgola decimale IT è normalizzata
    assert table.column("superficie").to_pylist() == [117.4, 208.5]
    assert table.column("attivo").to_pylist() == [True, False]
    assert r["dimensione_parquet"] == len(r["content"]) > 0


def test_migliaia_it_e_promozione_a_decimale() -> None:
    # "1.234" (migliaia IT) mescolato a "12,5" → colonna decimale, 1.234 = 1234
    csv = "comune;valore\nBari;1.234\nMonopoli;12,5\n"
    r = csv_to_parquet(csv)
    assert r["schema"][1] == {"nome": "valore", "tipo": "decimale"}
    assert _read_back(r["content"]).column("valore").to_pylist() == [1234.0, 12.5]


def test_colonna_mista_resta_testo_senza_perdita() -> None:
    csv = "codice\n123\nABC\n"
    r = csv_to_parquet(csv)
    assert r["schema"] == [{"nome": "codice", "tipo": "testo"}]
    assert _read_back(r["content"]).column("codice").to_pylist() == ["123", "ABC"]


def test_vuoti_diventano_null() -> None:
    csv = "n\n5\nn.d.\n7\n"
    r = csv_to_parquet(csv)
    assert r["schema"] == [{"nome": "n", "tipo": "intero"}]
    assert _read_back(r["content"]).column("n").to_pylist() == [5, None, 7]


def test_header_duplicati_e_righe_irregolari() -> None:
    csv = "a,a,\n1,2,3\n4,5\n"
    r = csv_to_parquet(csv)
    assert r["ok"] is True
    nomi = [c["nome"] for c in r["schema"]]
    assert nomi == ["a", "a_2", "colonna_3"]
    assert any("duplicata" in w for w in r["warnings"])
    assert any("numero di colonne diverso" in w for w in r["warnings"])
    # la riga corta è completata con null
    assert _read_back(r["content"]).column("colonna_3").to_pylist() == [3, None]


def test_file_vuoto() -> None:
    r = csv_to_parquet("   \n  ")
    assert r["ok"] is False
    assert "vuoto" in r["error"].lower()


def test_senza_pyarrow_degrada_con_errore_chiaro(monkeypatch: pytest.MonkeyPatch) -> None:
    # sys.modules["pyarrow"] = None fa fallire l'import lazy con ImportError
    monkeypatch.setitem(sys.modules, "pyarrow", None)
    r = csv_to_parquet("a\n1\n")
    assert r["ok"] is False
    assert "pyarrow" in r["error"]
    assert r["content"] is None
