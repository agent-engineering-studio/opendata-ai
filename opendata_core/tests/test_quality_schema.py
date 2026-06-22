"""Test dell'inferenza schema SQL + DDL (Data Quality Lab / Punto 03 #51)."""

from __future__ import annotations

from opendata_core.quality import infer_schema, profile_csv


def test_schema_tipi_e_chiave_primaria() -> None:
    csv = (
        "codice_istat,comune,popolazione,data_rilevazione\n"
        "072021,Gioia del Colle,27000,2023-01-01\n"
        "072006,Bari,320000,2023-01-01\n"
        "072011,Monopoli,49000,2023-01-01\n"
    )
    s = infer_schema(profile_csv(csv), table_name="Comuni Puglia")

    assert s["table_name"] == "comuni_puglia"  # sanificato
    types = {c["name"]: c["sql_type"] for c in s["columns"]}
    assert types["popolazione"] == "INTEGER"
    assert types["data_rilevazione"] == "DATE"
    assert types["comune"] == "TEXT"

    # codice_istat: univoco, senza vuoti, nome id-like → chiave primaria
    assert s["primary_key"] == "codice_istat"
    assert s["surrogate_key"] is False
    assert any(c["is_primary_key"] for c in s["columns"] if c["name"] == "codice_istat")

    assert s["ddl"].startswith("CREATE TABLE comuni_puglia (")
    assert "codice_istat INTEGER NOT NULL PRIMARY KEY" in s["ddl"]
    # colonna temporale → indice suggerito
    assert any(ix["column"] == "data_rilevazione" for ix in s["indexes"])
    assert "CREATE INDEX idx_comuni_puglia_data_rilevazione" in s["ddl"]


def test_schema_chiave_surrogata_e_nullable() -> None:
    # nessuna colonna univoca (valori ripetuti) + un vuoto → nullable + PK surrogata
    csv = "categoria,valore\nA,1\nA,2\nB,\n"
    s = infer_schema(profile_csv(csv))

    assert s["surrogate_key"] is True
    assert s["primary_key"] is None
    assert "id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY" in s["ddl"]

    valore = next(c for c in s["columns"] if c["name"] == "valore")
    assert valore["nullable"] is True  # ha un vuoto
    # categoria: TEXT a bassa cardinalità → indice categoriale
    assert any(ix["column"] == "categoria" for ix in s["indexes"])


def test_schema_nomi_sanificati_e_univoci() -> None:
    csv = "Anno;Anno;1\n2020;2021;x\n"  # duplicati + header numerico
    s = infer_schema(profile_csv(csv))
    names = [c["name"] for c in s["columns"]]
    assert len(names) == len(set(names))  # tutti univoci
    assert all(not n[0].isdigit() for n in names)  # nessun identificatore numerico
