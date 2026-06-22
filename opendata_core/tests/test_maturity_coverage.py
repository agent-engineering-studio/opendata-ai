"""Unit test su copertura tematica/settoriale e breakdown per dimensione (Fase A+B)."""

from __future__ import annotations

from datetime import datetime, timezone

from opendata_core.maturity import (
    DatasetInput,
    assess_coverage,
    assess_entity,
    classify_sector,
    coverage_template,
    infer_entity_type,
)

AS_OF = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _ds(i: int, *, title: str, theme: str | None = None, tags: list[str] | None = None) -> DatasetInput:
    return DatasetInput.from_ckan({
        "id": f"ds-{i}",
        "title": title,
        "notes": title,
        "tags": [{"name": t} for t in (tags or [])],
        "theme": theme,
        "license_id": "cc-by-4.0",
        "isopen": True,
        "metadata_modified": "2026-04-01T00:00:00",
        "frequency": "annual",
        "resources": [{"format": "CSV", "url": f"https://ex.it/{i}.csv"}],
    })


def test_classify_by_dcat_theme_code_has_precedence() -> None:
    ds = _ds(1, title="Qualcosa di generico", theme="TRAN")
    assert classify_sector(ds) == "TRAN"


def test_classify_by_keyword_fallback() -> None:
    assert classify_sector(_ds(1, title="Orari autobus del trasporto pubblico")) == "TRAN"
    assert classify_sector(_ds(2, title="Bilancio comunale e tributi IMU")) == "ECON"
    assert classify_sector(_ds(3, title="Raccolta differenziata rifiuti")) == "ENVI"
    assert classify_sector(_ds(4, title="Posti letto ospedale e farmacie")) == "HEAL"


def test_classify_unknown_returns_none() -> None:
    assert classify_sector(_ds(1, title="zxcvb qwerty")) is None


def test_infer_entity_type() -> None:
    assert infer_entity_type("Comune di Bari") == "comune"
    assert infer_entity_type("Regione Puglia") == "regione"
    assert infer_entity_type("Provincia di Lecce") == "provincia"
    assert infer_entity_type("Qualcosa", has_istat=True) == "comune"
    assert infer_entity_type("ARPA Puglia") == "ente"


def test_coverage_template_fallback() -> None:
    assert coverage_template("comune")  # non vuoto
    # tipo sconosciuto → fallback 'ente'
    assert coverage_template("pippo") == coverage_template("ente")


def test_assess_coverage_detects_missing_core_sectors() -> None:
    # Un comune con solo dataset di trasporti: mancano GOVE, ENVI, SOCI, ...
    datasets = [_ds(i, title="Orari trasporto pubblico", theme="TRAN") for i in range(3)]
    cov = assess_coverage(datasets, entity_type="comune")
    assert cov.entity_type == "comune"
    codes_missing = {s.code for s in cov.missing_core}
    assert "GOVE" in codes_missing and "TRAN" not in codes_missing
    # ordinati per priorità: GOVE (1) prima di EDUC (7)
    prios = [s.priority for s in cov.missing_core]
    assert prios == sorted(prios)
    assert 0.0 <= cov.coverage_score <= 100.0


def test_assess_coverage_full_core_scores_100() -> None:
    template = coverage_template("comune")
    datasets = [_ds(i, title=f"x {code}", theme=code) for i, code in enumerate(template)]
    cov = assess_coverage(datasets, entity_type="comune")
    assert cov.coverage_score == 100.0
    assert cov.missing_core == ()


def test_hvd_partial_coverage_reported() -> None:
    datasets = [
        _ds(1, title="Orari fermate autobus", theme="TRAN"),  # mobility
        _ds(2, title="Popolazione residente censimento", theme="SOCI"),  # statistics
    ] + [_ds(i, title="Bilancio comunale", theme="ECON") for i in range(3, 6)]
    cov = assess_coverage(datasets, entity_type="comune")
    assert "mobility" in cov.hvd_present
    assert "geospatial" in cov.hvd_missing
    assert len(cov.hvd_present) + len(cov.hvd_missing) == 6


def test_assess_entity_includes_coverage_and_breakdown() -> None:
    datasets = [_ds(i, title="Orari trasporto pubblico", theme="TRAN") for i in range(5)]
    res = assess_entity(datasets, as_of=AS_OF, entity_type="comune")
    assert res.coverage is not None
    assert res.coverage.entity_type == "comune"
    # breakdown: una voce per dimensione, con drivers ordinati crescenti
    assert {b.dimension for b in res.breakdown} == {"policy", "portal", "quality", "impact"}
    for b in res.breakdown:
        vals = [v for _, v in b.drivers]
        assert vals == sorted(vals)
    # raccomandazione di gap settoriale presente (mancano settori core)
    codes = {r.code for r in res.recommendations}
    assert "sector_gap" in codes


def test_coverage_recommendation_absent_when_full() -> None:
    template = coverage_template("comune")
    datasets = [_ds(i, title=f"x {code}", theme=code) for i, code in enumerate(template)] * 2
    res = assess_entity(datasets, as_of=AS_OF, entity_type="comune")
    codes = {r.code for r in res.recommendations}
    assert "sector_gap" not in codes
