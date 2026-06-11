"""Deterministic geographic post-filter tests.

The CKAN agent occasionally returns resources whose URL points at a different
comune than the one in the user query (national / multi-comune datasets, or
the LLM silently broadening scope). The filter is the safety net.
"""

from __future__ import annotations

from opendata_backend.orchestrator.geo_filter import (
    extract_places,
    filter_resources,
)
from opendata_backend.orchestrator.parsing import Resource


def _r(url: str, name: str = "") -> Resource:
    return Resource(name=name, url=url, format="UNKNOWN", source="ckan")


def test_extract_places_matches_capitalised_query():
    assert extract_places("piste ciclabili di Bologna") == {"bologna"}


def test_extract_places_handles_accents_and_punctuation():
    # The user is likely to write città, l'aquila, etc.
    assert "l aquila" in extract_places("metro de L'Aquila")
    # Hyphenated multi-word comune
    assert "reggio emilia" in extract_places(
        "ospedali della provincia di Reggio Emilia"
    )


def test_extract_places_empty_when_query_has_no_comune():
    assert extract_places("statistiche disoccupazione 2024") == set()


def test_filter_drops_off_comune_resource_when_query_names_a_city():
    # Reproduces the actual bug: query Bologna, agent returned a Genova zip.
    resources = [
        _r("https://opendata.comune.bologna.it/.../piste-ciclopedonali/exports/csv"),
        _r(
            "https://dati.emilia-romagna.it/.../pisteciclabilirg.kml",
            name="Piste ciclabili regionali",
        ),
        _r("https://opendatacomunegenova.s3.eu-south-1.amazonaws.com/risorse/piste_ciclabili.zip"),
    ]
    kept = filter_resources(resources, "piste ciclabili di Bologna")
    urls = {r.url for r in kept}
    assert any("bologna" in u for u in urls)
    assert any("emilia-romagna" in u for u in urls)  # regional, no comune → keep
    assert not any("genova" in u for u in urls), "Genova zip must be dropped"


def test_filter_no_op_when_query_has_no_comune():
    # Without a city in the query the filter has no scoping signal — pass through.
    resources = [
        _r("https://opendata.comune.bologna.it/x"),
        _r("https://opendatacomunegenova.s3/x"),
    ]
    kept = filter_resources(resources, "statistiche istat 2024")
    assert len(kept) == 2


def test_filter_keeps_resource_with_no_recognised_place():
    # National-level CKAN dataset URL — no city in URL, must be kept.
    resources = [
        _r("https://www.dati.gov.it/opendata/dataset/piste-ciclabili-italia.csv"),
    ]
    kept = filter_resources(resources, "piste ciclabili di Bologna")
    assert len(kept) == 1


def test_filter_keeps_resource_that_mentions_query_city_among_others():
    # A multi-comune resource that explicitly mentions the queried city counts
    # as in-scope — don't drop it just because another city is also named.
    resources = [
        _r("https://example.it/files/piste-bologna-modena.csv"),
    ]
    kept = filter_resources(resources, "piste ciclabili di Bologna")
    assert len(kept) == 1


# ── Region-scope filter ──────────────────────────────────────────────────


def test_filter_drops_off_region_resource_when_query_names_a_city():
    # Reproduces a real bug: query Bologna, agent returned a Friuli VG dataset
    # whose URL has the region name (no comune token) — the comune-only filter
    # missed it because FVG comuni aren't mentioned.
    resources = [
        _r("https://opendata.comune.bologna.it/.../piste-ciclopedonali/exports/csv"),
        _r(
            "https://www.dati.friuliveneziagiulia.it/api/views/7eat-pecq/rows.csv",
            name="Piste ciclabili FVG",
        ),
    ]
    kept = filter_resources(resources, "piste ciclabili di Bologna")
    urls = {r.url for r in kept}
    assert any("bologna" in u for u in urls)
    assert not any("friuliveneziagiulia" in u for u in urls), (
        "FVG resource must be dropped: different region from Bologna's"
    )


def test_filter_keeps_same_region_resource_for_a_city_query():
    # Bologna is in Emilia-Romagna → a regional Emilia-Romagna dataset is
    # legitimately in scope even though it doesn't name Bologna explicitly.
    resources = [
        _r(
            "https://dati.emilia-romagna.it/dataset/x/resource/y/pisteciclabilirg.kml",
            name="Piste ciclabili regionali",
        ),
    ]
    kept = filter_resources(resources, "piste ciclabili a Bologna")
    assert len(kept) == 1


def test_filter_region_check_handles_glued_domain():
    # Many regional portals concatenate the region name in the subdomain.
    resources = [
        _r("https://siciliaregione.it/dataset/foo"),  # off-region for Bologna
        _r("https://emiliaromagna.it/dataset/foo"),    # in-region for Bologna
    ]
    kept = filter_resources(resources, "piste ciclabili a Bologna")
    urls = {r.url for r in kept}
    assert any("emiliaromagna" in u for u in urls)
    assert not any("siciliaregione" in u for u in urls)


def test_filter_keeps_truly_national_resource_when_region_unknown():
    # No comune nor region in URL → keep, even if query has a city.
    resources = [
        _r("https://www.dati.gov.it/opendata/dataset/x/y.csv"),
    ]
    kept = filter_resources(resources, "piste ciclabili a Bologna")
    assert len(kept) == 1


def test_filter_drops_off_region_when_resource_names_only_another_region():
    # Symmetric case: query for Roma → drop a resource whose URL hints
    # explicitly at Lombardia (different region) without naming any comune.
    resources = [
        _r("https://www.dati.lombardia.it/dataset/foo"),
        _r("https://opendata.comune.roma.it/dataset/bar"),
    ]
    kept = filter_resources(resources, "trasporti pubblici Roma")
    urls = {r.url for r in kept}
    assert any("roma" in u for u in urls)
    assert not any("lombardia" in u for u in urls)
