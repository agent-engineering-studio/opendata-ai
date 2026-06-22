"""Test della gap analysis maturità (#50)."""

from __future__ import annotations

from opendata_core.maturity import (
    DimensionScores,
    Recommendation,
    analyze_gaps,
    odm_level,
)


def _scores(policy: float, portal: float, quality: float, impact: float, overall: float) -> DimensionScores:
    return DimensionScores(policy, portal, quality, impact, overall, odm_level(overall))


def _rec(code: str, dimension: str, severity: str = "media") -> Recommendation:
    return Recommendation(code=code, severity=severity, dimension=dimension, message=f"msg {code}", affected_count=1)


def test_prossimo_livello_e_punti() -> None:
    g = analyze_gaps(_scores(50, 50, 45, 40, 46), ())
    assert g.livello_attuale == "Follower"        # 46 ∈ [40,60)
    assert g.prossimo_livello == "Fast-tracker"   # soglia 60
    assert g.punti_al_prossimo == 14.0            # 60 - 46


def test_livello_massimo_nessun_prossimo() -> None:
    g = analyze_gaps(_scores(85, 85, 85, 85, 85), ())
    assert g.livello_attuale == "Trend-setter"
    assert g.prossimo_livello is None
    assert g.punti_al_prossimo is None


def test_collo_di_bottiglia_pesato() -> None:
    # quality ha peso 0.30 ed è bassa (30) → max peso×(100-score) ⇒ collo = quality
    g = analyze_gaps(_scores(90, 90, 30, 80, 70), ())
    assert g.collo_di_bottiglia == "quality"
    assert g.collo_di_bottiglia_label == "Qualità dei dati"


def test_quick_win_vs_strategico_e_ordine() -> None:
    recs = (
        _rec("sector_gap", "portal", "alta"),     # strategico
        _rec("open_license", "policy", "media"),  # quick-win
        _rec("dcat_ap_it", "quality", "bassa"),   # quick-win, sul collo (quality)
    )
    g = analyze_gaps(_scores(80, 80, 35, 80, 68), recs)
    assert g.collo_di_bottiglia == "quality"
    tipi = {a.code: a.tipo for a in g.azioni}
    assert tipi["open_license"] == "quick_win"
    assert tipi["dcat_ap_it"] == "quick_win"
    assert tipi["sector_gap"] == "strategico"
    # ordine: quick-win prima degli strategici; tra i quick-win, quello sul collo
    # di bottiglia (dcat_ap_it su quality) prima
    codes = [a.code for a in g.azioni]
    assert codes.index("dcat_ap_it") < codes.index("open_license") < codes.index("sector_gap")
    assert {a.code for a in g.quick_win} == {"open_license", "dcat_ap_it"}
    assert {a.code for a in g.strategiche} == {"sector_gap"}


def test_as_dict_serializzabile() -> None:
    g = analyze_gaps(_scores(50, 50, 45, 40, 46), (_rec("open_license", "policy"),))
    d = g.as_dict()
    assert d["prossimo_livello"] == "Fast-tracker"
    assert d["azioni"][0]["tipo"] == "quick_win"
    assert d["azioni"][0]["dimension_label"] == "Politiche e licenze"
