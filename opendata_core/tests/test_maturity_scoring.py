"""Unit test su aggregazione dimensioni, overall/livello ODM e raccomandazioni."""

from __future__ import annotations

from datetime import datetime, timezone

from opendata_core.maturity import (
    DEFAULT_WEIGHTS,
    DatasetInput,
    assess_entity,
    odm_level,
    score_dimensions,
)

AS_OF = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _good(i: int) -> dict:
    return {
        "id": f"good-{i}",
        "title": f"Dataset statistico {i}",
        "notes": "Descrizione completa e comprensibile.",
        "tags": [{"name": "statistica"}, {"name": "popolazione"}],
        "theme": "POP",
        "license_id": "cc-by-4.0",
        "isopen": True,
        "metadata_modified": "2026-04-01T00:00:00",
        "frequency": "annual",
        "resources": [{"format": "CSV", "url": f"https://ex.it/{i}.csv"}],
    }


def _bad(i: int) -> dict:
    return {
        "id": f"bad-{i}",
        "title": f"Documento {i}",
        "notes": "",
        "tags": [],
        "license_id": None,
        "isopen": False,
        "metadata_modified": "2021-01-01T00:00:00",
        "resources": [{"format": "PDF", "url": f"https://ex.it/{i}.pdf"}],
    }


def test_odm_level_thresholds() -> None:
    assert odm_level(0) == "Beginner"
    assert odm_level(39.9) == "Beginner"
    assert odm_level(40) == "Follower"
    assert odm_level(60) == "Fast-tracker"
    assert odm_level(85) == "Trend-setter"


def test_empty_entity_is_zero_beginner() -> None:
    ds = score_dimensions([], weights=DEFAULT_WEIGHTS)
    assert ds.overall == 0.0
    assert ds.level == "Beginner"


def test_all_good_entity_scores_high() -> None:
    datasets = [DatasetInput.from_ckan(_good(i)) for i in range(20)]
    res = assess_entity(datasets, as_of=AS_OF)
    assert res.n_datasets == 20
    for dim in (res.scores.policy, res.scores.portal, res.scores.quality, res.scores.impact):
        assert 0.0 <= dim <= 100.0
    assert res.scores.overall >= 60.0
    assert res.scores.level in {"Fast-tracker", "Trend-setter"}


def test_all_bad_entity_scores_low_with_recommendations() -> None:
    datasets = [DatasetInput.from_ckan(_bad(i)) for i in range(5)]
    res = assess_entity(datasets, as_of=AS_OF)
    assert res.scores.overall < 40.0
    assert res.scores.level == "Beginner"
    codes = {r.code for r in res.recommendations}
    assert {"open_license", "open_format", "freshness"} <= codes


def test_overall_is_weighted_sum() -> None:
    datasets = [DatasetInput.from_ckan(_good(i)) for i in range(3)] + [
        DatasetInput.from_ckan(_bad(i)) for i in range(3)
    ]
    res = assess_entity(datasets, as_of=AS_OF)
    s = res.scores
    expected = round(
        DEFAULT_WEIGHTS["policy"] * s.policy
        + DEFAULT_WEIGHTS["portal"] * s.portal
        + DEFAULT_WEIGHTS["quality"] * s.quality
        + DEFAULT_WEIGHTS["impact"] * s.impact,
        1,
    )
    assert abs(s.overall - expected) < 0.2


def test_dataset_quality_snapshot_present() -> None:
    res = assess_entity([DatasetInput.from_ckan(_good(1))], as_of=AS_OF)
    assert len(res.dataset_quality) == 1
    assert res.dataset_quality[0].dataset_id == "good-1"
