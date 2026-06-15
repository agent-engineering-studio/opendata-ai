"""Tests for the env-gated local-aggregates tool (`opencoesione_query_local`).

Seeds a file-based SQLite mirror of `oc_progetti` (the backend owns the real
table; here we reproduce its shape with plain SQL — no ORM import) and points
OPENCOESIONE_DB_URL at it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from opencoesione_mcp import local_db

_DDL = """
CREATE TABLE oc_progetti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clp TEXT NOT NULL,
    cod_comune TEXT NOT NULL DEFAULT '',
    cod_provincia TEXT,
    cod_regione TEXT,
    tema TEXT,
    ciclo TEXT,
    natura TEXT,
    stato TEXT,
    finanziamento_totale NUMERIC,
    pagamenti NUMERIC,
    titolo TEXT,
    soggetto_attuatore TEXT,
    raw TEXT,
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

_SEED = [
    # clp, comune, prov, reg, tema, ciclo, stato, fin, pag, attuatore
    ("P1", "072006", "072", "16", "Ambiente", "2014_2020", "Concluso", 1000.0, 900.0, "COMUNE DI BARI"),
    ("P2", "072006", "072", "16", "Trasporti e mobilità", "2014_2020", "In corso", 500.0, 100.0, "ANAS SPA"),
    ("P3", "072006", "072", "16", "Ambiente", "2021_2027", "Liquidato", 200.0, 200.0, "COMUNE DI BARI"),
    ("P4", "110002", "110", "16", "Ambiente", "2014_2020", "Concluso", 300.0, 150.0, "COMUNE DI BARLETTA"),
]


@pytest.fixture
def local_mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "oc.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(_DDL)
    conn.executemany(
        "INSERT INTO oc_progetti (clp, cod_comune, cod_provincia, cod_regione, tema, ciclo,"
        " stato, finanziamento_totale, pagamenti, soggetto_attuatore)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _SEED,
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv(local_db.DB_URL_ENV, f"sqlite:///{db_path}")
    return db_path


async def test_tool_not_registered_without_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(local_db.DB_URL_ENV, raising=False)
    from opencoesione_mcp.server import build_server

    tools = await build_server().list_tools()
    assert "opencoesione_query_local" not in {t.name for t in tools}


async def test_tool_registered_with_db_url(local_mirror: Path) -> None:
    from opencoesione_mcp.server import build_server

    tools = await build_server().list_tools()
    assert "opencoesione_query_local" in {t.name for t in tools}


async def _call(kind: str, **args):
    from opencoesione_mcp.server import build_server

    mcp = build_server()
    result = await mcp.call_tool("opencoesione_query_local", {"kind": kind, **args})
    return result[1]


async def test_capacity_full_dataset(local_mirror: Path) -> None:
    out = await _call("capacity", cod_comune="072006")
    cap = out["rows"]
    assert cap["progetti_totali"] == 3
    assert cap["progetti_conclusi"] == 2  # Concluso + Liquidato
    assert cap["finanziato_totale"] == pytest.approx(1700.0)
    assert cap["spend_ratio"] == pytest.approx(round(1200.0 / 1700.0, 4))
    assert "CC BY 4.0" in out["licenza"]
    assert out["sources"][0]["url"].startswith("https://opencoesione.gov.it")
    assert out["dataset"]["records"] == 4


async def test_capacity_with_ciclo_filter(local_mirror: Path) -> None:
    out = await _call("capacity", cod_comune="072006", ciclo="2014-2020")
    cap = out["rows"]
    assert cap["progetti_totali"] == 2
    assert cap["conclusi_ratio"] == pytest.approx(0.5)


async def test_spend_by_tema_orders_by_funding(local_mirror: Path) -> None:
    out = await _call("spend_by_tema", cod_comune="072006")
    rows = out["rows"]
    assert [r["tema"] for r in rows] == ["Ambiente", "Trasporti e mobilità"]
    assert rows[0]["finanziato"] == pytest.approx(1200.0)
    assert rows[0]["progetti"] == 2


async def test_top_soggetti_by_regione(local_mirror: Path) -> None:
    out = await _call("top_soggetti", cod_regione="16", limit=2)
    rows = out["rows"]
    assert rows[0]["soggetto_attuatore"] == "COMUNE DI BARI"
    assert rows[0]["progetti"] == 2
    assert len(rows) == 2


async def test_compare_comuni_with_slug_tema(local_mirror: Path) -> None:
    # 'trasporti' (API slug) must match the stored label 'Trasporti e mobilità'.
    out = await _call("compare_comuni", cod_comuni=["072006", "110002"], tema="trasporti")
    rows = out["rows"]
    by_comune = {r["cod_comune"]: r for r in rows}
    assert by_comune["072006"]["progetti"] == 1
    assert by_comune["110002"]["progetti"] == 0
    assert by_comune["072006"]["spend_ratio"] == pytest.approx(0.2)


async def test_missing_required_param_is_actionable(local_mirror: Path) -> None:
    from opencoesione_mcp.server import build_server

    mcp = build_server()
    with pytest.raises(Exception, match="cod_comune"):
        await mcp.call_tool("opencoesione_query_local", {"kind": "capacity"})
