"""Test dei consigli di scala/performance (Data Quality Lab / Punto 03 #51)."""

from __future__ import annotations

from opendata_core.quality import advise_scale, profile_csv


def _profile(n_rows: int) -> dict:
    rows = "".join(f"{i};BA;{i * 10};2021-01-01\n" for i in range(n_rows))
    return profile_csv("codice;provincia;valore;data\n" + rows)


def test_piccolo_nessun_accorgimento() -> None:
    s = advise_scale(_profile(20))
    assert s["dimensione"]["classe"] == "piccolo"
    assert [c["codice"] for c in s["consigli"]] == ["ok"]


def test_grande_parquet_partizione_indici_esposizione() -> None:
    # forza la classe "grande" via size_bytes (evita di generare 100k righe)
    s = advise_scale(_profile(50), size_bytes=60 * 1024 * 1024)
    assert s["dimensione"]["classe"] == "grande"
    assert s["dimensione"]["stimata"] is False
    codici = {c["codice"] for c in s["consigli"]}
    assert "parquet" in codici
    assert "partizione_tempo" in codici          # c'è una colonna data
    assert "indici" in codici
    assert "esposizione" in codici
    # la partizione temporale cita la colonna data
    part = next(c for c in s["consigli"] if c["codice"] == "partizione_tempo")
    assert "data" in part["titolo"]


def test_medio_parquet_ma_no_partizione() -> None:
    s = advise_scale(_profile(50), size_bytes=8 * 1024 * 1024)
    assert s["dimensione"]["classe"] == "medio"
    codici = {c["codice"] for c in s["consigli"]}
    assert "parquet" in codici
    assert "partizione_tempo" not in codici  # il partizionamento è solo per "grande"
    assert "esposizione" not in codici


def test_dimensione_stimata_quando_size_assente() -> None:
    s = advise_scale(_profile(20))
    assert s["dimensione"]["stimata"] is True
    assert s["dimensione"]["leggibile"]
