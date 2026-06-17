"""Unit test deterministici sul motore di valore (art. 14) + combinabilità."""

from __future__ import annotations

from datetime import datetime, timezone

from opendata_core.maturity import DatasetInput
from opendata_core.value import combinability, estimate_value

AS_OF = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _pkg(**over):
    base = {
        "id": "d1",
        "title": "Mobilità urbana per comune",
        "notes": "Dataset con gli orari del trasporto pubblico locale, le fermate e le linee del comune, aggiornato ogni anno.",
        "tags": [{"name": "mobilità"}, {"name": "istat"}],
        "theme": "TRA",
        "license_id": "cc-by-4.0",
        "isopen": True,
        "metadata_modified": "2026-03-01T00:00:00",
        "frequency": "annual",
        "resources": [{"format": "CSV", "url": "https://ex.it/tpl.csv"}],
    }
    base.update(over)
    return base


def test_value_high_for_hvd_open_combinable() -> None:
    v = estimate_value(DatasetInput.from_ckan(_pkg()), as_of=AS_OF)
    assert v.hvd_category == "mobility"
    assert v.socioeconomic == 100.0          # HVD + theme + descrizione ricca
    assert v.audience_sme == 100.0           # licenza aperta + formato aperto + machine-readable
    assert v.combinability > 0
    assert 0.0 <= v.overall <= 100.0


def test_value_low_for_bare_closed() -> None:
    bare = {"id": "d2", "title": "Doc", "notes": "", "tags": [], "isopen": False,
            "resources": [{"format": "PDF", "url": "https://ex.it/d.pdf"}]}
    v = estimate_value(DatasetInput.from_ckan(bare), as_of=AS_OF)
    assert v.audience_sme == 0.0
    assert v.overall < 30.0


def test_overall_is_mean_of_four() -> None:
    v = estimate_value(DatasetInput.from_ckan(_pkg()), as_of=AS_OF)
    expected = round((v.socioeconomic + v.audience_sme + v.revenue + v.combinability) / 4.0, 1)
    assert v.overall == expected


def test_reuse_score_passthrough_not_in_overall() -> None:
    base = DatasetInput.from_ckan(_pkg())
    v0 = estimate_value(base, as_of=AS_OF)
    v1 = estimate_value(base, reuse_score=88.0, as_of=AS_OF)
    assert v1.reuse_score == 88.0
    assert v1.overall == v0.overall  # reuse non altera l'overall art. 14


def test_combinability_detects_spatial_and_temporal() -> None:
    c = combinability(DatasetInput.from_ckan(_pkg()))
    assert c.has_spatial          # "istat"/"comune"
    assert c.has_temporal         # "anno" + frequenza
    assert c.score == 100.0       # spaziale + temporale + formato aperto

    geo = _pkg(title="Confini", notes="", tags=[], theme=None, frequency=None,
               resources=[{"format": "GeoJSON", "url": "https://ex.it/c.geojson"}])
    cg = combinability(DatasetInput.from_ckan(geo))
    assert "formato-geo" in cg.spatial_keys


def test_combinability_none_for_aspatial() -> None:
    flat = {"id": "x", "title": "Elenco generico", "notes": "testo", "tags": [],
            "resources": [{"format": "PDF", "url": "https://ex.it/x.pdf"}]}
    c = combinability(DatasetInput.from_ckan(flat))
    assert not c.has_spatial
    assert not c.has_temporal
    assert c.score == 0.0
