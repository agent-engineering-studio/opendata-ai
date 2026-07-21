"""Idee regionali (#230) — priorità = valore pesato dal gap di copertura."""

from __future__ import annotations

from opendata_core.region import ComuneSummary, IdeaCandidate, regional_ideas


def _comuni() -> list[ComuneSummary]:
    return [
        ComuneSummary(istat="1", nome="A", hvd_categorie=["geospatial", "mobility"]),
        ComuneSummary(istat="2", nome="B", hvd_categorie=["geospatial"]),
        ComuneSummary(istat="3", nome="C", hvd_categorie=[]),
        ComuneSummary(istat="4", nome="D", hvd_categorie=[]),
    ]


def _candidates() -> list[IdeaCandidate]:
    return [
        # alto valore, categoria mancante in 4/4 comuni → priorità massima
        IdeaCandidate(id="rifiuti", nome="Rifiuti", area="ambiente", hvd="earth_observation_environment", valore=80),
        # alto valore ma già coperto in 2/4 (geospatial) → priorità media
        IdeaCandidate(id="pug", nome="PUG", area="territorio", hvd="geospatial", valore=80),
        # senza HVD → gap neutro
        IdeaCandidate(id="albo", nome="Albo", area="atti", hvd=None, valore=40),
    ]


def test_missing_everywhere_ranks_first() -> None:
    ideas = regional_ideas(_candidates(), _comuni(), comuni_totali=4)
    assert ideas[0].id == "rifiuti"
    assert ideas[0].comuni_mancanti == 4
    assert ideas[0].copertura == 0.0
    assert "4/4" in ideas[0].motivo


def test_covered_candidate_ranks_lower_than_missing_same_value() -> None:
    ideas = {i.id: i for i in regional_ideas(_candidates(), _comuni(), comuni_totali=4)}
    # stesso valore (80) ma pug è coperto in 2/4 → priorità < rifiuti
    assert ideas["pug"].comuni_con == 2
    assert ideas["pug"].copertura == 0.5
    assert ideas["pug"].priorita < ideas["rifiuti"].priorita


def test_no_hvd_candidate_is_measured_as_unknown_coverage() -> None:
    ideas = {i.id: i for i in regional_ideas(_candidates(), _comuni(), comuni_totali=4)}
    albo = ideas["albo"]
    assert albo.comuni_con is None and albo.copertura is None
    assert "non misurabile" in albo.motivo


def test_sorted_by_priority_desc() -> None:
    ideas = regional_ideas(_candidates(), _comuni(), comuni_totali=4)
    prios = [i.priorita for i in ideas]
    assert prios == sorted(prios, reverse=True)


def test_empty_region_safe() -> None:
    ideas = regional_ideas(_candidates(), [], comuni_totali=0)
    # total 0 → copertura non misurabile, nessun crash
    assert all(i.priorita >= 0 for i in ideas)
