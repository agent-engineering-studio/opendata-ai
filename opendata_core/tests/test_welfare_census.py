"""Test del connettore Welfare comunale (ISTAT 8milaCensus, gruppo P, cens. 2011)."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from opendata_core.census import fetch_welfare_comune
from opendata_core.census import lavoro, welfare

_BASE = "https://ottomilacensus.istat.it/fileadmin/download"

_PROV_CSV = (
    "AnnoCP;Livello territoriale;Codice Regione 2011;Codice Provincia 2011;"
    "Codice comune 2011;Denominazione del territorio\n"
    "2011;2;16;72;;Bari\n"
)

# header con i codici P (Popolazione) + righe comune (latin-1, ';', decimali con virgola)
_CONF_HDR = (
    "AnnoCP;Livello territoriale;Codice Regione 2011;Codice Provincia 2011;"
    "Codice comune 2011;Denominazione del territorio;"
    "P1;P7;P8;P9;P10;P11;P12;P13"
)
_CONF_CSV = "\n".join([
    _CONF_HDR,
    # Gioia del Colle 2011 (valori reali dal codebook)
    "2011;1;16;72;72021;Gioia del Colle;27889;133,5;94,4;5,1;10,8;31,8;20,3;157,1",
    # stesso comune anno 2001 → DEVE essere ignorato
    "2001;1;16;72;72021;Gioia del Colle;26000;130,0;95,0;5,5;9,0;28,0;22,0;130,0",
    # comune senza indici demografici (tutti '-') → trovato False
    "2011;1;16;72;72011;Casamassima;20000;100,0;96,0;6,0;8,0;-;-;-",
]) + "\n"


def _reset() -> None:
    lavoro._prov_region = None
    lavoro._region_index_cache.clear()
    welfare._result_cache.clear()


def _mock_files(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{_BASE}/Province_Regioni_Italia_confini_2011.csv",
        content=_PROV_CSV.encode("latin-1"), is_reusable=True,
    )
    httpx_mock.add_response(
        url=f"{_BASE}/16/confini/confini_16.csv",
        content=_CONF_CSV.encode("latin-1"), is_reusable=True,
    )


async def test_fetch_welfare_comune_happy(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_files(httpx_mock)
    res = await fetch_welfare_comune("072021")

    assert res["trovato"] is True
    assert res["anno"] == "2011"
    assert res["popolazione"] == 27889            # P1 (intero), anno 2011 non 2001
    assert res["indice_vecchiaia"] == 157.1        # P13
    assert res["indice_dipendenza_anziani"] == 31.8   # P11
    assert res["indice_dipendenza_giovanile"] == 20.3  # P12
    assert res["indice_dipendenza_strutturale"] == 52.1  # P11 + P12
    assert res["pct_over_75"] == 10.8              # P10
    assert "confini_16.csv" in res["source_url"]
    assert res["sources"][0]["licenza"].startswith("ISTAT 8milaCensus")


async def test_fetch_welfare_comune_no_indices(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_files(httpx_mock)
    res = await fetch_welfare_comune("072011")  # indici demografici tutti mancanti
    assert res["trovato"] is False
    assert "source_url" in res


async def test_fetch_welfare_comune_absent(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_files(httpx_mock)
    res = await fetch_welfare_comune("072999")  # provincia mappata, comune assente
    assert res["trovato"] is False
