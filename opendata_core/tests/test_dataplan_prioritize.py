"""Test della prioritizzazione valore×sforzo del Copilota Open Data (#173, D2)."""

from __future__ import annotations

from opendata_core.dataplan import CandidateDataset, load_catalog, prioritize
from opendata_core.dataplan.models import GiaAperto


def _c(id_: str, **kw) -> CandidateDataset:
    base = dict(nome=id_, area="X", fonte_interna="f", descrizione="d")
    base.update(kw)
    return CandidateDataset(id=id_, **base)


def test_ranking_is_deterministic() -> None:
    cat = load_catalog()
    r1 = prioritize(cat)
    r2 = prioritize(cat)
    assert [x.candidate.id for x in r1] == [x.candidate.id for x in r2]
    assert len(r1) == len(cat)


def test_quick_wins_come_first() -> None:
    ranked = prioritize(load_catalog())
    # i primi risultati sono quick win; nessun "basso_valore" prima di un quick win
    quads = [r.quadrante for r in ranked]
    assert quads[0] == "quick_win"
    first_low = next((i for i, q in enumerate(quads) if q == "basso_valore"), len(quads))
    last_quick = max((i for i, q in enumerate(quads) if q == "quick_win"), default=-1)
    assert last_quick < first_low
    # gli adempimenti nazionali già aperti (solo link) sono quick win in testa
    top_ids = {r.candidate.id for r in ranked[:6]}
    assert "bilancio-siope" in top_ids and "appalti-anac" in top_ids


def test_gia_aperto_is_low_effort_and_valued() -> None:
    r = prioritize([_c("nat", hvd="statistics",
                       gia_aperto=GiaAperto(fonte="BDAP", connettore="x"))])[0]
    assert r.sforzo == 1  # "solo link"
    assert r.quadrante == "quick_win"
    assert "linkarlo" in r.motivazione


def test_personal_data_raises_effort() -> None:
    # stesso sforzo dichiarato "alto", ma privacy personale → sforzo effettivo maggiore
    pers = prioritize([_c("p", hvd="geospatial", sforzo="alto", privacy="personale")])[0]
    pub = prioritize([_c("q", hvd="geospatial", sforzo="alto", privacy="nullo")])[0]
    assert pers.sforzo > pub.sforzo
    assert "de-identificazione" in pers.motivazione


def test_reuse_signal_increases_value() -> None:
    senza = prioritize([_c("a", hvd="geospatial")])[0]
    con = prioritize([_c("b", hvd="geospatial", sblocca=["lente x", "report y"])])[0]
    assert con.valore > senza.valore


def test_reuse_boost_injection() -> None:
    # una "domanda di riuso non soddisfatta" iniettata dà più peso a quel dataset
    base = prioritize([_c("z", hvd="statistics")])[0].valore
    boosted = prioritize([_c("z", hvd="statistics")], reuse_boost={"z": 2})[0].valore
    assert boosted > base


def test_high_value_high_effort_is_strategico() -> None:
    # PUG: HVD + sblocca suolo ma sforzo medio → strategico (non quick win)
    pug = next(r for r in prioritize(load_catalog()) if r.candidate.id == "pug-zonizzazione")
    assert pug.quadrante in ("strategico", "quick_win")
    assert pug.valore >= 55  # alto valore (HVD + riuso)
