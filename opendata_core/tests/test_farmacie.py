"""Test del connettore Sanità (Ministero della Salute — anagrafe farmacie)."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from opendata_core.salute import fetch_farmacie_comune
from opendata_core.salute import farmacie

_PAGE = "https://www.dati.salute.gov.it/it/dataset/farmacie/"
_CSV_URL = "https://www.dati.salute.gov.it/sites/default/files/opendata/FRM_FARMA_5_20260621.csv"
_PAGE_HTML = (
    '<html><body><a href="/sites/default/files/opendata/FRM_FARMA_5_20260621.csv">CSV</a>'
    '<a href="/sites/default/files/opendata/FRM_FARMA_5_20260621.xml">XML</a></body></html>'
)

_HDR = (
    "cod_farmacia;cod_farmacia_asl;indirizzo;descrizione_farmacia;p_iva;cap;cod_comune;"
    "comune;frazione;cod_provincia;sigla_provincia;provincia;cod_regione;regione;"
    "data_inizio_validita;data_fine_validita;descrizione_tipologia;codice_tipologia;"
    "latitudine;longitudine;localizzazione"
)


def _row(cod_comune: str, fine: str, tip_desc: str, tip_cod: str) -> str:
    # 21 colonne; riempiamo solo quelle lette dal parser, il resto placeholder.
    return ";".join([
        "1", "00000", "Via X", "FARMACIA Y", "00000000000", "70023", cod_comune,
        "COMUNE", "-", cod_comune[:3], "BA", "BARI", "160", "PUGLIA",
        "01/01/2013", fine, tip_desc, tip_cod, "40,7", "16,9", "1",
    ])


_CSV = "\n".join([
    _HDR,
    _row("072021", "-", "Ordinaria", "1"),                 # valida
    _row("072021", "-", "Ordinaria", "1"),                 # valida
    _row("072021", "30/06/2017", "Ordinaria", "1"),        # CESSATA → esclusa
    _row("072021", "-", "Dispensario", "2"),               # valida (altra tipologia)
    _row("058091", "-", "Ordinaria", "1"),                 # altro comune (Roma)
    _row("ABC", "-", "Ordinaria", "1"),                    # cod_comune malformato → escluso
]) + "\n"


def _reset() -> None:
    farmacie._index_cache.clear()
    farmacie._result_cache.clear()


def _mock_ok(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=_PAGE, text=_PAGE_HTML, is_reusable=True)
    httpx_mock.add_response(url=_CSV_URL, content=_CSV.encode("latin-1"), is_reusable=True)


async def test_fetch_farmacie_comune_happy(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_ok(httpx_mock)
    res = await fetch_farmacie_comune("072021")
    assert res["trovato"] is True
    assert res["farmacie_totali"] == 3                       # 2 Ordinaria valide + 1 Dispensario
    assert res["per_tipologia"] == {"Ordinaria": 2, "Dispensario": 1}
    assert res["source_url"] == _PAGE
    assert res["sources"][0]["licenza"].startswith("Ministero della Salute")


async def test_fetch_farmacie_comune_excludes_cessate(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_ok(httpx_mock)
    res = await fetch_farmacie_comune("058091")  # Roma: 1 Ordinaria valida
    assert res["trovato"] is True
    assert res["farmacie_totali"] == 1


async def test_fetch_farmacie_comune_absent(httpx_mock: HTTPXMock) -> None:
    _reset()
    _mock_ok(httpx_mock)
    res = await fetch_farmacie_comune("072011")  # comune senza farmacie nel CSV
    assert res["trovato"] is False
    assert "source_url" in res


async def test_fetch_farmacie_comune_invalid_istat(httpx_mock: HTTPXMock) -> None:
    _reset()
    res = await fetch_farmacie_comune("ABC")  # nessuna fetch: codice non valido
    assert res["trovato"] is False


async def test_fetch_farmacie_comune_source_unavailable(httpx_mock: HTTPXMock) -> None:
    _reset()
    # pagina dataset senza link al CSV → fonte non risolvibile.
    httpx_mock.add_response(url=_PAGE, text="<html><body>no link</body></html>", is_reusable=True)
    res = await fetch_farmacie_comune("072021")
    assert res["trovato"] is False
