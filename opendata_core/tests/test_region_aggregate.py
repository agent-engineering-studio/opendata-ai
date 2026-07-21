"""Motore di aggregazione regionale (#228) — deterministico, dati iniettati."""

from __future__ import annotations

from opendata_core.region import ComuneSummary, aggregate_region


def _comuni() -> list[ComuneSummary]:
    return [
        # maturo (overall ≥ 80, ≥5 dataset)
        ComuneSummary(istat="072001", nome="Alfa", overall=85.0, n_dataset=20,
                      dimensioni={"policy": 80, "quality": 90}, hvd_categorie=["geospatial", "mobility"]),
        # in_crescita (40 ≤ overall < 80)
        ComuneSummary(istat="072002", nome="Beta", overall=55.0, n_dataset=8,
                      dimensioni={"policy": 30, "quality": 70}, hvd_categorie=["geospatial"]),
        # pochi_dati (overall < 40)
        ComuneSummary(istat="072003", nome="Gamma", overall=20.0, n_dataset=3,
                      dimensioni={"policy": 10, "quality": 40}, hvd_categorie=[]),
        # zero_dati (nessun dato, non valutato)
        ComuneSummary(istat="072004", nome="Delta", overall=None, n_dataset=0),
    ]


def test_distribuzione_stato_uses_state_machine() -> None:
    ov = aggregate_region(_comuni(), regione="Puglia", cod_regione="16")
    assert ov.distribuzione_stato == {
        "zero_dati": 1, "pochi_dati": 1, "in_crescita": 1, "maturo": 1
    }
    assert ov.comuni_totali == 4
    assert ov.comuni_valutati == 3  # Delta ha overall None


def test_comuni_totali_override_counts_missing_as_zero() -> None:
    # La regione ha 10 comuni ma solo 4 hanno una sintesi → 6 in più zero_dati.
    ov = aggregate_region(_comuni(), regione="Puglia", cod_regione="16", comuni_totali=10)
    assert ov.comuni_totali == 10
    assert ov.distribuzione_stato["zero_dati"] == 1 + 6


def test_mediana_overall_only_over_assessed() -> None:
    ov = aggregate_region(_comuni(), regione="Puglia", cod_regione="16")
    assert ov.mediana_overall == 55.0  # median(85, 55, 20)


def test_hvd_copertura_fractions() -> None:
    ov = aggregate_region(_comuni(), regione="Puglia", cod_regione="16")
    # geospatial: Alfa+Beta = 2/4; mobility: Alfa = 1/4; meteorological: 0/4
    assert ov.hvd_copertura["geospatial"] == 0.5
    assert ov.hvd_copertura["mobility"] == 0.25
    assert ov.hvd_copertura["meteorological"] == 0.0


def test_dimensioni_mediana() -> None:
    ov = aggregate_region(_comuni(), regione="Puglia", cod_regione="16")
    # policy: median(80,30,10)=30 ; quality: median(90,70,40)=70
    assert ov.dimensioni_mediana["policy"] == 30.0
    assert ov.dimensioni_mediana["quality"] == 70.0


def test_dove_intervenire_zero_data_first_then_weak_dimension() -> None:
    ov = aggregate_region(_comuni(), regione="Puglia", cod_regione="16")
    comuni_hints = [h for h in ov.dove_intervenire if h.tipo == "comune"]
    dim_hints = [h for h in ov.dove_intervenire if h.tipo == "dimensione"]
    # Delta (nessun dato) è il primo suggerimento comune.
    assert comuni_hints[0].istat == "072004"
    assert comuni_hints[0].motivo == "nessun dato pubblicato"
    # Gamma (overall 20 < 40) tra i comuni; Beta/Alfa (≥40 / maturo) NO.
    ids = {h.istat for h in comuni_hints}
    assert "072003" in ids and "072001" not in ids and "072002" not in ids
    # policy (mediana 30 < 50) è segnalata debole; quality (70) no.
    weak_dims = {h.dimensione for h in dim_hints}
    assert "policy" in weak_dims and "quality" not in weak_dims


def test_empty_region_is_safe() -> None:
    ov = aggregate_region([], regione="Molise", cod_regione="14", comuni_totali=136)
    assert ov.comuni_valutati == 0
    assert ov.mediana_overall is None
    assert ov.distribuzione_stato["zero_dati"] == 136
    assert all(v == 0.0 for v in ov.hvd_copertura.values())
    assert ov.dove_intervenire == []
