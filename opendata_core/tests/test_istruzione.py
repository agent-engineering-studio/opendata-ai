"""Test del connettore Grado di Istruzione (ISTAT 8milaCensus, censimento 2011)."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from opendata_core.census import fetch_grado_istruzione_comune
from opendata_core.census import istruzione, lavoro

_BASE = "https://ottomilacensus.istat.it/fileadmin/download"

# Province_Regioni: provincia 72 (Bari) → regione 16 (Puglia)
_PROV_CSV = (
    "AnnoCP;Livello territoriale;Codice Regione 2011;Codice Provincia 2011;"
    "Codice comune 2011;Denominazione del territorio\n"
    "2011;2;16;72;;Bari\n"
)

# confini_16 con i codici del gruppo I (istruzione) + righe comune (latin-1, ';', virgola)
_CONF_HDR = (
    "AnnoCP;Livello territoriale;Codice Regione 2011;Codice Provincia 2011;"
    "Codice comune 2011;Denominazione del territorio;I2;I4;I5;I6;I7;I9"
)
_CONF_CSV = "\n".join([
    _CONF_HDR,
    # Gioia del Colle 2011 (anno target)
    "2011;1;16;72;72021;Gioia del Colle;5,1;0,8;12,3;38,4;18,9;30,2",
    # stesso comune 2001 → DEVE essere ignorato
    "2001;1;16;72;72021;Gioia del Colle;3,0;1,5;18,0;30,0;12,0;35,0",
    # comune con istruzione tutta mancante ('-') → trovato False
    "2011;1;16;72;72011;Casamassima;-;-;-;-;-;-",
]) + "\n"


def _reset() -> None:
    lavoro._prov_region = None
    lavoro._region_index_cache.clear()
    istruzione._result_cache.clear()


def _mock(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/Province_Regioni_Italia_confini_2011.csv",
        content=_PROV_CSV.encode("latin-1"), is_reusable=True,
    )
    httpx_mock.add_response(
        url=f"{_BASE}/16/confini/confini_16.csv",
        content=_CONF_CSV.encode("latin-1"), is_reusable=True,
    )


async def test_fetch_grado_istruzione_happy(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock(httpx_mock)
    res = await fetch_grado_istruzione_comune("072021")
    assert res["trovato"] is True
    assert res["anno"] == "2011"
    assert res["incidenza_laureati_30_34"] == 18.9       # I7 (anno 2011, non 2001)
    assert res["incidenza_diploma_o_laurea_25_64"] == 38.4  # I6
    assert res["incidenza_licenza_media_25_64"] == 30.2  # I9
    assert res["incidenza_analfabeti"] == 0.8            # I4
    assert res["uscita_precoce_15_24"] == 12.3           # I5
    assert "confini_16.csv" in res["source_url"]
    assert res["sources"][0]["licenza"].startswith("ISTAT 8milaCensus")


async def test_fetch_grado_istruzione_all_missing(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock(httpx_mock)
    res = await fetch_grado_istruzione_comune("072011")  # Casamassima, tutto '-'
    assert res["trovato"] is False
    assert "source_url" in res


async def test_fetch_grado_istruzione_absent(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock(httpx_mock)
    res = await fetch_grado_istruzione_comune("072999")  # provincia mappata, comune assente
    assert res["trovato"] is False


async def test_fetch_grado_istruzione_province_unmapped(httpx_mock: HTTPXMock) -> None:
    _reset()
    httpx_mock.add_response(
        url=f"{_BASE}/Province_Regioni_Italia_confini_2011.csv",
        content=_PROV_CSV.encode("latin-1"), is_reusable=True,
    )
    res = await fetch_grado_istruzione_comune("001059")  # provincia 1 non mappata
    assert res["trovato"] is False
