"""Test del connettore Lavoro (ISTAT 8milaCensus, censimento 2011)."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from opendata_core.census import fetch_lavoro_comune
from opendata_core.census import lavoro

_BASE = "https://ottomilacensus.istat.it/fileadmin/download"

# Province_Regioni: provincia 72 (Bari) → regione 16 (Puglia)
_PROV_CSV = (
    "AnnoCP;Livello territoriale;Codice Regione 2011;Codice Provincia 2011;"
    "Codice comune 2011;Denominazione del territorio\n"
    "2011;2;16;72;;Bari\n"
    "2001;2;16;72;;Bari\n"
)

# confini_16: header con i codici L + righe comune (latin-1, ';', decimali con virgola)
_CONF_HDR = (
    "AnnoCP;Livello territoriale;Codice Regione 2011;Codice Provincia 2011;"
    "Codice comune 2011;Denominazione del territorio;"
    "L3;L4;L8;L9;L12;L14;L15;L16;L17;L18;L19;L20;L21"
)
_CONF_CSV = "\n".join([
    _CONF_HDR,
    # Gioia del Colle 2011 (anno target)
    "2011;1;16;72;72021;Gioia del Colle;45,8;23,4;13,5;36,5;39,6;34,0;12,4;22,0;47,7;17,9;28,3;22,3;17,0",
    # stesso comune anno 2001 → DEVE essere ignorato
    "2001;1;16;72;72021;Gioia del Colle;40,0;20,0;10,0;30,0;42,0;36,0;15,0;25,0;45,0;15,0;25,0;20,0;20,0",
    # comune con un indicatore mancante ('-')
    "2011;1;16;72;72011;Casamassima;44,0;-;12,0;30,0;41,0;33,0;5,0;30,0;50,0;15,0;30,0;18,0;22,0",
]) + "\n"


def _reset() -> None:
    lavoro._prov_region = None
    lavoro._region_index_cache.clear()
    lavoro._result_cache.clear()


def _mock_prov(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/Province_Regioni_Italia_confini_2011.csv",
        content=_PROV_CSV.encode("latin-1"), is_reusable=True,
    )


def _mock_files(httpx_mock: HTTPXMock) -> None:
    _mock_prov(httpx_mock)
    httpx_mock.add_response(
        url=f"{_BASE}/16/confini/confini_16.csv",
        content=_CONF_CSV.encode("latin-1"), is_reusable=True,
    )


async def test_fetch_lavoro_comune_happy(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_files(httpx_mock)
    res = await fetch_lavoro_comune("072021")

    assert res["trovato"] is True
    assert res["anno"] == "2011"
    assert res["tasso_occupazione"] == 39.6          # L12 (anno 2011, non il 2001)
    assert res["tasso_disoccupazione_giovanile"] == 36.5  # L9
    assert res["neet_15_29"] == 23.4                 # L4
    assert res["tasso_attivita"] == 45.8             # L3
    assert res["settori"]["commercio"] == 17.9       # L18
    assert res["competenze"]["alta_media"] == 28.3   # L19
    assert "confini_16.csv" in res["source_url"]
    assert res["sources"][0]["licenza"].startswith("ISTAT 8milaCensus")


async def test_fetch_lavoro_comune_missing_value(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_files(httpx_mock)
    res = await fetch_lavoro_comune("072011")  # Casamassima, NEET = '-'
    assert res["trovato"] is True
    assert res["neet_15_29"] is None
    assert res["tasso_disoccupazione"] == 12.0


async def test_fetch_lavoro_comune_absent(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_files(httpx_mock)
    res = await fetch_lavoro_comune("072999")  # provincia 72 (mappata) ma comune assente
    assert res["trovato"] is False
    assert "source_url" in res


async def test_fetch_lavoro_comune_province_unmapped(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_prov(httpx_mock)  # solo il file province: confini non viene scaricato
    res = await fetch_lavoro_comune("001059")  # provincia 1 non nel file Province_Regioni
    assert res["trovato"] is False
