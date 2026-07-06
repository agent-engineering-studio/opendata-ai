"""Test della normalizzazione: lookup table + viste (Data Quality Lab #51)."""

from __future__ import annotations

from opendata_core.quality import build_normalization


def test_lookup_table_generata_per_colonna_categoriale_ripetuta() -> None:
    righe = "".join(f"{i},{'Nord' if i % 2 == 0 else 'Sud'},2021-01-01\n" for i in range(20))
    r = build_normalization("id,zona,data\n" + righe)
    lkp = {t["colonna_originale"]: t for t in r["tabelle_lookup"]}
    assert "zona" in lkp
    assert lkp["zona"]["n_valori"] == 2
    assert "CREATE TABLE lkp_zona" in lkp["zona"]["ddl"]
    assert "Nord" in lkp["zona"]["insert_sql"] and "Sud" in lkp["zona"]["insert_sql"]


def test_nessun_lookup_se_valori_tutti_diversi() -> None:
    righe = "".join(f"{i},valore_unico_{i}\n" for i in range(10))
    r = build_normalization("id,descrizione\n" + righe)
    assert r["tabelle_lookup"] == []


def test_vista_totali_per_categoria() -> None:
    righe = "".join(f"{i},{'A' if i % 3 else 'B'}\n" for i in range(15))
    r = build_normalization("id,tipo\n" + righe, table_name="miei_dati")
    viste = {v["tipo"]: v for v in r["viste"]}
    assert "totali_categoria" in viste
    assert "CREATE VIEW v_totali_tipo" in viste["totali_categoria"]["ddl"]
    assert "FROM miei_dati" in viste["totali_categoria"]["ddl"]


def test_vista_serie_storica_da_colonna_data() -> None:
    righe = "".join(f"{i},2020-01-01\n" if i < 5 else f"{i},2021-01-01\n" for i in range(10))
    r = build_normalization("id,data_evento\n" + righe)
    serie = [v for v in r["viste"] if v["tipo"] == "serie_storica"]
    assert len(serie) == 1
    assert "EXTRACT(YEAR FROM data_evento)" in serie[0]["ddl"]


def test_pivot_categoria_per_anno_quando_entrambe_presenti() -> None:
    righe = "".join(
        f"{i},{'A' if i % 2 else 'B'},{'2020-01-01' if i < 10 else '2021-01-01'}\n" for i in range(20)
    )
    r = build_normalization("id,tipo,data\n" + righe)
    pivot = [v for v in r["viste"] if v["tipo"] == "pivot"]
    assert len(pivot) == 1
    assert "FILTER (WHERE tipo" in pivot[0]["ddl"]


def test_dataset_senza_normalizzazione_applicabile() -> None:
    r = build_normalization("id,valore\n1,10\n2,20\n3,30\n")
    assert r["tabelle_lookup"] == []
    assert r["viste"] == []
    assert r["note"]


def test_file_vuoto() -> None:
    r = build_normalization("")
    assert r == {"tabelle_lookup": [], "viste": [], "note": ["File vuoto."]}
