"""Unit test deterministici sul calcolo qualità (5-star/FAIR/DCAT/ISO/HVD)."""

from __future__ import annotations

from datetime import datetime, timezone

from opendata_core.maturity import DatasetInput, assess_quality, match_hvd_category

AS_OF = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _pkg(**over):
    base = {
        "id": "d1",
        "title": "Popolazione residente",
        "notes": "Serie storica della popolazione del comune.",
        "tags": [{"name": "popolazione"}, {"name": "demografia"}],
        "theme": "POP",
        "license_id": "cc-by-4.0",
        "isopen": True,
        "metadata_modified": "2026-03-01T10:00:00",
        "frequency": "annual",
        "resources": [{"format": "CSV", "url": "https://ex.it/pop.csv"}],
    }
    base.update(over)
    return base


def test_five_star_open_csv_is_three() -> None:
    q = assess_quality(DatasetInput.from_ckan(_pkg()), as_of=AS_OF)
    assert q.stars_5 == 3
    assert q.license_open is True


def test_five_star_zero_without_open_license() -> None:
    q = assess_quality(
        DatasetInput.from_ckan(_pkg(isopen=False, license_id="proprietaria")), as_of=AS_OF
    )
    assert q.stars_5 == 0


def test_five_star_proprietary_structured_is_two() -> None:
    q = assess_quality(
        DatasetInput.from_ckan(_pkg(resources=[{"format": "XLSX", "url": "https://ex.it/p.xlsx"}])),
        as_of=AS_OF,
    )
    assert q.stars_5 == 2


def test_five_star_rdf_is_four_linked_is_five() -> None:
    rdf = assess_quality(
        DatasetInput.from_ckan(_pkg(resources=[{"format": "RDF", "url": "https://ex.it/p.rdf"}])),
        as_of=AS_OF,
    )
    assert rdf.stars_5 == 4
    linked = assess_quality(
        DatasetInput.from_ckan(
            _pkg(resources=[
                {"format": "RDF", "url": "https://ex.it/p.rdf"},
                {"format": "SPARQL", "url": "https://ex.it/sparql"},
            ])
        ),
        as_of=AS_OF,
    )
    assert linked.stars_5 == 5


def test_fair_high_for_rich_dataset() -> None:
    q = assess_quality(DatasetInput.from_ckan(_pkg()), as_of=AS_OF)
    assert q.fair_f == 1.0          # id+title+notes+tags+theme
    assert q.fair_mean >= 0.8


def test_fair_low_for_bare_dataset() -> None:
    bare = {"id": "d2", "title": "", "resources": []}
    q = assess_quality(DatasetInput.from_ckan(bare), as_of=AS_OF)
    assert q.fair_mean < 0.3
    assert q.dcat_ap_it < 0.3


def test_dcat_compliance_full() -> None:
    q = assess_quality(DatasetInput.from_ckan(_pkg()), as_of=AS_OF)
    assert q.dcat_ap_it == 1.0


def test_freshness_and_currency() -> None:
    fresh = assess_quality(DatasetInput.from_ckan(_pkg()), as_of=AS_OF)
    assert fresh.freshness_days == 91  # 2026-03-01T10:00 → 2026-06-01T00:00 = 91 giorni pieni
    assert fresh.iso25012_detail["currency"] == 1.0
    stale = assess_quality(
        DatasetInput.from_ckan(_pkg(metadata_modified="2023-01-01T00:00:00")), as_of=AS_OF
    )
    assert stale.freshness_days > 365
    assert stale.iso25012_detail["currency"] < 1.0


def test_semantic_clarity_raises_completeness() -> None:
    base = DatasetInput.from_ckan(_pkg())
    without = assess_quality(base, as_of=AS_OF)
    with_sem = assess_quality(base, semantic_clarity=1.0, as_of=AS_OF)
    assert with_sem.iso25012_detail["completeness"] >= without.iso25012_detail["completeness"]


def test_hvd_category_match() -> None:
    assert match_hvd_category(DatasetInput.from_ckan(_pkg())) == "statistics"
    mob = _pkg(title="Orari TPL e fermate autobus", tags=[{"name": "mobilità"}], theme="TRA")
    assert match_hvd_category(DatasetInput.from_ckan(mob)) == "mobility"
    none = _pkg(title="Sagra della cipolla", notes="evento", tags=[], theme=None)
    assert match_hvd_category(DatasetInput.from_ckan(none)) is None
