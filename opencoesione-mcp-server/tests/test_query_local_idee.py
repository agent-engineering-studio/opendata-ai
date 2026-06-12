"""Tests dei kind comparativi (similar_projects / gap_by_tema / stalled_projects).

Mirror SQLite con oc_progetti + comuni_anagrafica (creata via SQL piano, come
fa il backend con le migrazioni). Peer group: stessa regione, pop 0.5×–2×.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from opencoesione_mcp import local_db

_DDL_PROGETTI = """
CREATE TABLE oc_progetti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clp TEXT NOT NULL, cod_comune TEXT NOT NULL DEFAULT '',
    cod_provincia TEXT, cod_regione TEXT,
    tema TEXT, ciclo TEXT, natura TEXT, stato TEXT,
    finanziamento_totale NUMERIC, pagamenti NUMERIC,
    titolo TEXT, soggetto_attuatore TEXT, raw TEXT,
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""
_DDL_ANAGRAFICA = """
CREATE TABLE comuni_anagrafica (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_comune TEXT NOT NULL UNIQUE, nome TEXT NOT NULL,
    cod_provincia TEXT, cod_regione TEXT, popolazione INTEGER,
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

# Barletta (94k) — peer: Bisceglie (55k, stessa regione, in fascia),
# Bari (316k, FUORI fascia 2×), Matera (60k ma regione 17 → esclusa).
_ANAGRAFICA = [
    ("110002", "Barletta", "110", "16", 94000),
    ("110003", "Bisceglie", "110", "16", 55000),
    ("072006", "Bari", "072", "16", 316000),
    ("077014", "Matera", "077", "17", 60000),
]

_PROGETTI = [
    # Bisceglie (peer): tema Energia con buon ratio — materia per gap/similar.
    ("PEER1", "110003", "16", "Energia", "2014_2020", "Concluso", 1000.0, 950.0, "Comunità energetica PIP", "COMUNE DI BISCEGLIE"),
    ("PEER2", "110003", "16", "Energia", "2014_2020", "Concluso", 800.0, 700.0, "Fotovoltaico capannoni", "COMUNE DI BISCEGLIE"),
    # Bari (fuori fascia): non deve entrare nei peer.
    ("BARI1", "072006", "16", "Energia", "2014_2020", "Concluso", 5000.0, 5000.0, "Mega progetto", "COMUNE DI BARI"),
    # Barletta: nessun progetto Energia (gap!), uno Ambiente fermo (stalled).
    ("LOC1", "110002", "16", "Ambiente", "2014_2020", "In corso", 2000.0, 100.0, "Bonifica ferma", "COMUNE DI BARLETTA"),
    ("LOC2", "110002", "16", "Ambiente", "2014_2020", "Concluso", 500.0, 500.0, "Parco concluso", "COMUNE DI BARLETTA"),
]


@pytest.fixture
def mirror_with_anagrafica(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "oc.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(_DDL_PROGETTI)
    conn.execute(_DDL_ANAGRAFICA)
    conn.executemany(
        "INSERT INTO comuni_anagrafica (cod_comune, nome, cod_provincia, cod_regione,"
        " popolazione) VALUES (?, ?, ?, ?, ?)", _ANAGRAFICA,
    )
    conn.executemany(
        "INSERT INTO oc_progetti (clp, cod_comune, cod_regione, tema, ciclo, stato,"
        " finanziamento_totale, pagamenti, titolo, soggetto_attuatore)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", _PROGETTI,
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv(local_db.DB_URL_ENV, f"sqlite:///{db}")
    return db


@pytest.fixture
def mirror_without_anagrafica(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "oc_no_ana.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(_DDL_PROGETTI)
    conn.commit()
    conn.close()
    monkeypatch.setenv(local_db.DB_URL_ENV, f"sqlite:///{db}")
    return db


async def test_peer_group_band_and_region(mirror_with_anagrafica: Path) -> None:
    pg = await local_db.peer_group("110002")
    codes = {p["cod_comune"] for p in pg["peers"]}
    assert codes == {"110003"}  # Bari fuori fascia, Matera fuori regione
    assert "stessa regione" in pg["criteri"] and "0.5×" in pg["criteri"]


async def test_similar_projects_orders_by_ratio(mirror_with_anagrafica: Path) -> None:
    out = await local_db.similar_projects("110002", tema="energia")
    titoli = [p["titolo"] for p in out["progetti"]]
    assert titoli == ["Comunità energetica PIP", "Fotovoltaico capannoni"]
    assert out["progetti"][0]["spend_ratio"] == pytest.approx(0.95)
    assert out["progetti"][0]["comune"] == "Bisceglie"
    assert "criteri" in out  # i criteri del peer group sono dichiarati


async def test_gap_by_tema_finds_energia(mirror_with_anagrafica: Path) -> None:
    out = await local_db.gap_by_tema("110002", min_peers=1)
    temi = {g["tema"] for g in out["gap"]}
    assert temi == {"Energia"}  # Ambiente no: Barletta ha già progetti
    g = out["gap"][0]
    assert g["comuni_peer_attivi"] == 1 and g["progetti_peer"] == 2
    assert g["finanziato_medio"] == pytest.approx(900.0)


async def test_stalled_projects_below_threshold(mirror_with_anagrafica: Path) -> None:
    out = await local_db.stalled_projects("110002", soglia_ratio=0.2)
    assert [p["clp"] for p in out["progetti"]] == ["LOC1"]
    assert out["progetti"][0]["spend_ratio"] == pytest.approx(0.05)


async def test_missing_anagrafica_is_actionable(mirror_without_anagrafica: Path) -> None:
    with pytest.raises(local_db.AnagraficaMissing, match="comuni-sync"):
        await local_db.peer_group("110002")


async def test_tool_dispatch_for_new_kinds(mirror_with_anagrafica: Path) -> None:
    from opencoesione_mcp.server import build_server

    mcp = build_server()
    result = await mcp.call_tool(
        "opencoesione_query_local",
        {"kind": "gap_by_tema", "cod_comune": "110002", "min_peers": 1},
    )
    payload = result[1]
    assert payload["kind"] == "gap_by_tema"
    assert payload["rows"]["gap"][0]["tema"] == "Energia"
    assert "CC BY 4.0" in payload["licenza"]
