"""Test del connettore BDAP/SIOPE — bilanci comunali (#100)."""

from __future__ import annotations

import re

from opendata_core.bdap import fetch_bilancio_comune
from opendata_core.bdap import client as bdap_client

_BASE = "https://bdap-opendata.rgs.mef.gov.it"

# Campo → valore, per costruire righe OData realistiche nei test.
_F = {
    "provincia": bdap_client._F_PROVINCIA,
    "comune": bdap_client._F_COMUNE,
    "denom": bdap_client._F_DENOMINAZIONE,
    "mese": bdap_client._F_ANNO_MESE,
    "titolo": bdap_client._F_CODICE_TITOLO,
    "descr": bdap_client._F_DESCRIZIONE_TITOLO,
    "pop": bdap_client._F_POPOLAZIONE,
    "importo": bdap_client._F_IMPORTO,
}


def _reset() -> None:
    bdap_client._index_cache.clear()
    bdap_client._odata_cache.clear()
    bdap_client._result_cache.clear()


def _atom_feed(rows: list[dict[str, str]]) -> str:
    entries = []
    for row in rows:
        props = "".join(f"<d:{k}>{v}</d:{k}>" for k, v in row.items())
        entries.append(
            "<entry><content type=\"application/xml\">"
            f"<m:properties>{props}</m:properties></content></entry>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" '
        'xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">'
        + "".join(entries) + "</feed>"
    )


def _package_search_page(results: list[dict]) -> dict:
    return {"success": True, "result": {"count": len(results), "results": results}}


def _pkg(pkg_id: str, title: str) -> dict:
    return {"id": pkg_id, "name": title.lower().replace(" ", "-"), "title": title}


def _package_show(resources: list[dict]) -> dict:
    return {"success": True, "result": {"resources": resources}}


def _odata_resource(resource_id: str) -> dict:
    return {
        "resource_type": "OData",
        "format": "XML",
        "url": f"{_BASE}/ODataProxy/MdData('{resource_id}@rgs')/DataRows",
    }


def test_parse_title_extracts_anno_regione_tipo() -> None:
    parsed = bdap_client._parse_title("2024 - Puglia - SIOPE Movimenti cumulati mensili di Spesa")
    assert parsed == (2024, "Puglia", "Spesa")


def test_parse_title_rejects_unrelated_dataset() -> None:
    assert bdap_client._parse_title("2024 - Prima Nota di Variazione Approvata") is None


def test_aggregate_per_titolo_keeps_latest_month() -> None:
    rows = [
        {
            _F["denom"]: "COMUNE DI GIOIA DEL COLLE", _F["pop"]: "26502.00",
            _F["titolo"]: "E1000000000", _F["descr"]: "Entrate tributarie",
            _F["mese"]: "2024/01", _F["importo"]: "100.00",
        },
        {
            _F["denom"]: "COMUNE DI GIOIA DEL COLLE", _F["pop"]: "26502.00",
            _F["titolo"]: "E1000000000", _F["descr"]: "Entrate tributarie",
            _F["mese"]: "2024/06", _F["importo"]: "469076.56",
        },
    ]
    voci, denom, pop = bdap_client._aggregate_per_titolo(rows)
    assert len(voci) == 1
    assert voci[0]["importo_cumulato"] == 469076.56  # mese più recente, non sommato
    assert voci[0]["mese_riferimento"] == "2024/06"
    assert denom == "COMUNE DI GIOIA DEL COLLE"
    assert pop == 26502.0


async def test_fetch_bilancio_happy(httpx_mock) -> None:
    _reset()
    entrata_id, spesa_id = "pkg-entrata-2024", "pkg-spesa-2024"
    httpx_mock.add_response(
        url=re.compile(r".*package_search.*"),
        json=_package_search_page([
            _pkg(entrata_id, "2024 - Puglia - SIOPE Movimenti cumulati mensili di Entrata"),
            _pkg(spesa_id, "2024 - Puglia - SIOPE Movimenti cumulati mensili di Spesa"),
        ]),
    )
    httpx_mock.add_response(
        url=re.compile(rf".*package_show.*id={entrata_id}.*"),
        json=_package_show([_odata_resource("res-entrata")]),
    )
    httpx_mock.add_response(
        url=re.compile(rf".*package_show.*id={spesa_id}.*"),
        json=_package_show([_odata_resource("res-spesa")]),
    )
    httpx_mock.add_response(
        url=re.compile(r".*res-entrata.*"),
        text=_atom_feed([{
            _F["denom"]: "COMUNE DI GIOIA DEL COLLE", _F["pop"]: "26502.00",
            _F["titolo"]: "E1000000000", _F["descr"]: "Entrate tributarie",
            _F["mese"]: "2024/06", _F["importo"]: "469076.56",
        }]),
        headers={"Content-Type": "application/atom+xml"},
    )
    httpx_mock.add_response(
        url=re.compile(r".*res-spesa.*"),
        text=_atom_feed([{
            _F["denom"]: "COMUNE DI GIOIA DEL COLLE", _F["pop"]: "26502.00",
            _F["titolo"]: "U1000000000", _F["descr"]: "Spese correnti",
            _F["mese"]: "2024/06", _F["importo"]: "300000.00",
        }]),
        headers={"Content-Type": "application/atom+xml"},
    )

    res = await fetch_bilancio_comune("072021", anno=2024)
    assert res["trovato"] is True
    assert res["anno"] == 2024
    assert res["denominazione"] == "COMUNE DI GIOIA DEL COLLE"
    assert res["popolazione"] == 26502.0
    assert res["totale_entrate"] == 469076.56
    assert res["totale_spese"] == 300000.00
    assert res["entrate"][0]["descrizione"] == "Entrate tributarie"
    assert res["sources"][0]["licenza"].startswith("BDAP")


async def test_fetch_bilancio_paginates_search(httpx_mock) -> None:
    """L'indice deve paginare package_search finché una pagina torna < page size."""
    _reset()
    full_page = [_pkg(f"filler-{i}", f"2020 - Lazio - Rendiconto {i}") for i in range(100)]
    last_page = [_pkg("pkg-e", "2024 - Puglia - SIOPE Movimenti cumulati mensili di Entrata")]
    httpx_mock.add_response(url=re.compile(r".*package_search.*start=0.*"), json=_package_search_page(full_page))
    httpx_mock.add_response(url=re.compile(r".*package_search.*start=100.*"), json=_package_search_page(last_page))
    httpx_mock.add_response(
        url=re.compile(r".*package_show.*id=pkg-e.*"),
        json=_package_show([_odata_resource("res-e")]),
    )
    httpx_mock.add_response(
        url=re.compile(r".*res-e.*"),
        text=_atom_feed([{
            _F["denom"]: "COMUNE DI GIOIA DEL COLLE", _F["pop"]: "26502.00",
            _F["titolo"]: "E1000000000", _F["descr"]: "Entrate tributarie",
            _F["mese"]: "2024/01", _F["importo"]: "1.00",
        }]),
        headers={"Content-Type": "application/atom+xml"},
    )

    res = await fetch_bilancio_comune("072021", anno=2024)
    assert res["trovato"] is True
    assert res["totale_spese"] == 0.0  # nessun dataset "Spesa" nell'indice per il 2024


async def test_fetch_bilancio_year_fallback(httpx_mock) -> None:
    """Nessuna riga nel 2025 (comune non SIOPE-aderente) → retrocede al 2024."""
    _reset()
    httpx_mock.add_response(
        url=re.compile(r".*package_search.*"),
        json=_package_search_page([
            _pkg("pkg-e-2025", "2025 - Puglia - SIOPE Movimenti cumulati mensili di Entrata"),
            _pkg("pkg-e-2024", "2024 - Puglia - SIOPE Movimenti cumulati mensili di Entrata"),
        ]),
    )
    httpx_mock.add_response(
        url=re.compile(r".*package_show.*id=pkg-e-2025.*"),
        json=_package_show([_odata_resource("res-2025")]),
    )
    httpx_mock.add_response(url=re.compile(r".*res-2025.*"), text=_atom_feed([]), headers={"Content-Type": "application/atom+xml"})
    httpx_mock.add_response(
        url=re.compile(r".*package_show.*id=pkg-e-2024.*"),
        json=_package_show([_odata_resource("res-2024")]),
    )
    httpx_mock.add_response(
        url=re.compile(r".*res-2024.*"),
        text=_atom_feed([{
            _F["denom"]: "COMUNE DI GIOIA DEL COLLE", _F["pop"]: "26502.00",
            _F["titolo"]: "E1000000000", _F["descr"]: "Entrate tributarie",
            _F["mese"]: "2024/12", _F["importo"]: "500000.00",
        }]),
        headers={"Content-Type": "application/atom+xml"},
    )

    res = await fetch_bilancio_comune("072021", anno=2025)
    assert res["trovato"] is True
    assert res["anno"] == 2024


async def test_fetch_bilancio_nessun_anno_disponibile(httpx_mock) -> None:
    _reset()
    httpx_mock.add_response(url=re.compile(r".*package_search.*"), json=_package_search_page([]))
    res = await fetch_bilancio_comune("072021", anno=2024)
    assert res["trovato"] is False
    assert "anno" not in res


async def test_fetch_bilancio_provincia_non_mappata() -> None:
    _reset()
    res = await fetch_bilancio_comune("999021")
    assert res["trovato"] is False


async def test_fetch_bilancio_codice_non_valido() -> None:
    res = await fetch_bilancio_comune("abc")
    assert res["trovato"] is False
