"""Test del connettore Casa/Abitazioni (ISTAT 8milaCensus, censimento 2011)."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from opendata_core.census import fetch_casa_comune
from opendata_core.census import casa, lavoro

_BASE = "https://ottomilacensus.istat.it/fileadmin/download"

# Province_Regioni: provincia 72 (Bari) → regione 16 (Puglia)
_PROV_CSV = (
    "AnnoCP;Livello territoriale;Codice Regione 2011;Codice Provincia 2011;"
    "Codice comune 2011;Denominazione del territorio\n"
    "2011;2;16;72;;Bari\n"
)

# confini_16 con i codici del gruppo A (abitazioni) + righe comune (latin-1, ';', virgola)
_CONF_HDR = (
    "AnnoCP;Livello territoriale;Codice Regione 2011;Codice Provincia 2011;"
    "Codice comune 2011;Denominazione del territorio;A1;A4;A6;A7;A12;A14"
)
_CONF_CSV = "\n".join([
    _CONF_HDR,
    # Gioia del Colle 2011 (anno target) — valori reali verificati sul dato ISTAT
    "2011;1;16;72;72021;Gioia del Colle;74,3;11,8;28,7;98,2;41,7;0,3",
    # stesso comune 2001 → DEVE essere ignorato
    "2001;1;16;72;72021;Gioia del Colle;60,0;20,0;15,0;80,0;30,0;5,0",
    # comune con indicatori abitativi tutti mancanti ('-') → trovato False
    "2011;1;16;72;72011;Casamassima;-;-;-;-;-;-",
]) + "\n"


def _reset() -> None:
    lavoro._prov_region = None
    lavoro._region_index_cache.clear()
    casa._result_cache.clear()


def _mock(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/Province_Regioni_Italia_confini_2011.csv",
        content=_PROV_CSV.encode("latin-1"), is_reusable=True,
    )
    httpx_mock.add_response(
        url=f"{_BASE}/16/confini/confini_16.csv",
        content=_CONF_CSV.encode("latin-1"), is_reusable=True,
    )


async def test_fetch_casa_happy(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock(httpx_mock)
    res = await fetch_casa_comune("072021")
    assert res["trovato"] is True
    assert res["anno"] == "2011"
    assert res["incidenza_proprieta"] == 74.3               # A1 (anno 2011, non 2001)
    assert res["abitazioni_non_occupate_centri"] == 11.8    # A4
    assert res["eta_media_patrimonio_recente"] == 28.7      # A6
    assert res["disponibilita_servizi"] == 98.2             # A7
    assert res["superficie_media_per_occupante"] == 41.7    # A12
    assert res["affollamento_abitazioni"] == 0.3            # A14
    assert "confini_16.csv" in res["source_url"]
    assert res["sources"][0]["licenza"].startswith("ISTAT 8milaCensus")


async def test_fetch_casa_all_missing(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock(httpx_mock)
    res = await fetch_casa_comune("072011")  # Casamassima, tutto '-'
    assert res["trovato"] is False
    assert "source_url" in res


async def test_fetch_casa_absent(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock(httpx_mock)
    res = await fetch_casa_comune("072999")  # provincia mappata, comune assente
    assert res["trovato"] is False


async def test_fetch_casa_province_unmapped(httpx_mock: HTTPXMock) -> None:
    _reset()
    httpx_mock.add_response(
        url=f"{_BASE}/Province_Regioni_Italia_confini_2011.csv",
        content=_PROV_CSV.encode("latin-1"), is_reusable=True,
    )
    res = await fetch_casa_comune("001059")  # provincia 1 non mappata
    assert res["trovato"] is False


async def test_fetch_casa_non_numeric_code() -> None:
    res = await fetch_casa_comune("abc")
    assert res["trovato"] is False
