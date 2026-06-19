"""Test del connettore Welfare (ISTAT DCIS_POPRES1 — struttura per età → indici)."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from opendata_core.sdmx import fetch_welfare_comune
from opendata_core.sdmx import welfare

_HEADER = "DATAFLOW,FREQ,ITTER107,TIPO_DATO15,ETA1,SEXISTAT1,STATCIV2,TIME_PERIOD,OBS_VALUE"


def _row(eta: str, anno: str, val: str) -> str:
    # labels=both rende le dimensioni come 'CODE: Label'; TIME/OBS sono nudi.
    return (
        f"IT1:22_289,A: annuale,072021: Gioia del Colle,JAN: pop 1 gennaio,"
        f"{eta},9: totale,99: totale,{anno},{val}"
    )


# 0-14 = 200 ; 15-64 = 600 ; 65+ = 150+50 = 200 ; TOTAL = 1000.
# Y_GE65 è una classe AGGREGATA: deve essere IGNORATA (no doppio conteggio).
# La riga 2019 deve essere ignorata (si prende l'anno più recente = 2023).
_CSV_OK = "\n".join([
    _HEADER,
    _row("Y5: 5 anni", "2023", "100"),
    _row("Y10: 10 anni", "2023", "100"),
    _row("Y40: 40 anni", "2023", "300"),
    _row("Y50: 50 anni", "2023", "300"),
    _row("Y70: 70 anni", "2023", "150"),
    _row("Y_GE100: 100 anni e oltre", "2023", "50"),
    _row("TOTAL: totale", "2023", "1000"),
    _row("Y_GE65: 65 anni e oltre", "2023", "999"),  # aggregato → ignorato
    _row("Y40: 40 anni", "2019", "1"),               # anno vecchio → ignorato
]) + "\n"

# Senza riga TOTAL: il totale si ricava sommando le fasce.
_CSV_NO_TOTAL = "\n".join([
    _HEADER,
    _row("Y5: 5 anni", "2023", "100"),
    _row("Y40: 40 anni", "2023", "600"),
    _row("Y70: 70 anni", "2023", "300"),
]) + "\n"


def _reset() -> None:
    welfare._cache.clear()


async def test_fetch_welfare_comune_happy(httpx_mock: HTTPXMock) -> None:
    _reset()
    httpx_mock.add_response(text=_CSV_OK, is_reusable=True)
    res = await fetch_welfare_comune("072021")

    assert res["trovato"] is True
    assert res["anno"] == "2023"
    assert res["popolazione"] == 1000
    assert res["pop_0_14"] == 200
    assert res["pop_15_64"] == 600
    assert res["pop_65_piu"] == 200          # Y70 + Y_GE100, NON Y_GE65 (aggregato)
    assert res["indice_vecchiaia"] == 100.0  # 200 / 200 * 100
    assert res["indice_dipendenza_anziani"] == 33.3   # 200 / 600 * 100
    assert res["indice_dipendenza_strutturale"] == 66.7  # 400 / 600 * 100
    assert res["pct_over_65"] == 20.0
    assert res["pct_under_15"] == 20.0
    assert "22_289" in res["source_url"]
    assert res["sources"][0]["licenza"].startswith("ISTAT")


async def test_fetch_welfare_comune_no_total_row(httpx_mock: HTTPXMock) -> None:
    _reset()
    httpx_mock.add_response(text=_CSV_NO_TOTAL, is_reusable=True)
    res = await fetch_welfare_comune("072021")
    assert res["trovato"] is True
    assert res["popolazione"] == 1000        # 100 + 600 + 300 (scommato dalle fasce)
    assert res["indice_vecchiaia"] == 300.0  # 300 / 100 * 100


async def test_fetch_welfare_comune_absent(httpx_mock: HTTPXMock) -> None:
    _reset()
    httpx_mock.add_response(text=_HEADER + "\n", is_reusable=True)  # solo header, 0 righe
    res = await fetch_welfare_comune("072999")
    assert res["trovato"] is False
    assert "source_url" in res


async def test_fetch_welfare_comune_cached(httpx_mock: HTTPXMock) -> None:
    _reset()
    httpx_mock.add_response(text=_CSV_OK)  # NON riusabile: una sola risposta
    a = await fetch_welfare_comune("072021")
    b = await fetch_welfare_comune("072021")  # deve arrivare dalla cache
    assert a == b
    assert a["trovato"] is True
