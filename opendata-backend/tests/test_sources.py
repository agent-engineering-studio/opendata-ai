"""Test di resolve_source_url (fonti chiare display-only): file/API → origine,
OSM nascosto, portali noti → pagina riconoscibile, OpenCoesione progetto tenuto."""

from __future__ import annotations

from opendata_backend.orchestrator.sources import resolve_source_url, source_level


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
    ) == ("https://esploradati.istat.it/", "ISTAT — esploradati (SDMX)")
    assert resolve_source_url(
        "https://ottomilacensus.istat.it/fileadmin/download/x.csv"
    ) == ("https://ottomilacensus.istat.it/", "ISTAT 8milaCensus")


def test_opencoesione_project_page_is_kept() -> None:
    assert resolve_source_url(
        "https://opencoesione.gov.it/it/api/progetti/ABC123.json"
    ) == ("https://opencoesione.gov.it/it/progetti/abc123/", "OpenCoesione — progetto")
    # aggregati/JSON → homepage (mai il link profondo)
    assert resolve_source_url(
        "https://opencoesione.gov.it/it/api/aggregati/territori/comune-x.json"
    ) == ("https://opencoesione.gov.it/", "OpenCoesione")


def test_source_level_labels_territorial_granularity() -> None:
    # Fonti delle lenti territoriali → comunale (granularità d'uso nell'analisi).
    assert source_level("https://idrogeo.isprambiente.it/api/pir/comuni/72021") == "comunale"
    assert source_level("https://dati.istruzione.it/opendata/.../SCUANAGRAFESTAT.csv") == "comunale"
    assert source_level("https://www.dati.salute.gov.it/it/dataset/farmacie/") == "comunale"
    assert source_level("https://esploradati.istat.it/SDMXWS/rest/data/183_285/x") == "comunale"
    assert source_level("https://opencoesione.gov.it/it/progetti/abc/") == "comunale"
    assert source_level("https://www.openstreetmap.org/#map=13/40/16") == "comunale"
    # Sovra-nazionali → etichettati come tali.
    assert source_level("https://ec.europa.eu/eurostat/x") == "europeo"
    assert source_level("https://data.oecd.org/x") == "internazionale"
    # Host sconosciuto / URL non valido → nessuna etichetta.
    assert source_level("https://comune.z.it/turismo") is None
    assert source_level(None) is None


def test_clean_urls_and_non_http_are_dropped() -> None:
    assert resolve_source_url(None) is None
    assert resolve_source_url("") is None
    assert resolve_source_url("ftp://x.it/file") is None
    # Pagina pulita sconosciuta → tenuta così com'è.
    assert resolve_source_url("https://comune.z.it/turismo") == (
        "https://comune.z.it/turismo", "comune.z.it"
    )
