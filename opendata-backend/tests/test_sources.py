"""Test di resolve_source_url (fonti chiare display-only): file/API → origine,
OSM nascosto, portali noti → pagina riconoscibile, OpenCoesione progetto tenuto."""

from __future__ import annotations

from opendata_backend.orchestrator.sources import resolve_source_url


def test_osm_and_overpass_are_hidden() -> None:
    assert resolve_source_url("https://www.openstreetmap.org/relation/12345") is None
    assert resolve_source_url("https://overpass-api.de/api/interpreter?data=x") is None


def test_file_and_api_collapse_to_origin() -> None:
    # CSV profondo di un portale comunale sconosciuto → origine del sito.
    assert resolve_source_url("https://dati.comune.x.it/download/foo.csv?token=9") == (
        "https://dati.comune.x.it/", "dati.comune.x.it"
    )
    # API path → origine.
    assert resolve_source_url("https://portale.y.it/api/v1/data") == (
        "https://portale.y.it/", "portale.y.it"
    )


def test_known_portals_map_to_landing() -> None:
    assert resolve_source_url(
        "https://esploradati.istat.it/SDMXWS/rest/data/22_289/all"
    ) == ("https://www.istat.it/", "ISTAT")
    assert resolve_source_url(
        "https://ottomilacensus.istat.it/fileadmin/download/x.csv"
    ) == ("https://www.istat.it/", "ISTAT")


def test_opencoesione_project_page_is_kept() -> None:
    assert resolve_source_url(
        "https://opencoesione.gov.it/it/api/progetti/ABC123.json"
    ) == ("https://opencoesione.gov.it/it/progetti/abc123/", "OpenCoesione — progetto")
    # aggregati/JSON → homepage (mai il link profondo)
    assert resolve_source_url(
        "https://opencoesione.gov.it/it/api/aggregati/territori/comune-x.json"
    ) == ("https://opencoesione.gov.it/", "OpenCoesione")


def test_clean_urls_and_non_http_are_dropped() -> None:
    assert resolve_source_url(None) is None
    assert resolve_source_url("") is None
    assert resolve_source_url("ftp://x.it/file") is None
    # Pagina pulita sconosciuta → tenuta così com'è.
    assert resolve_source_url("https://comune.z.it/turismo") == (
        "https://comune.z.it/turismo", "comune.z.it"
    )
