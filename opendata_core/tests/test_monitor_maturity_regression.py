"""Test del check di regressione maturità (monitoraggio #88 → avvisi #103)."""

from __future__ import annotations

from opendata_core.monitor import check_maturity_regression


def _codes(findings: list[dict]) -> set[str]:
    return {f["codice"] for f in findings}


def test_primo_assessment_nessun_confronto() -> None:
    r = check_maturity_regression(
        overall_attuale=55.0, overall_precedente=None,
        livello_attuale="Follower", livello_precedente=None,
    )
    assert r == []


def test_calo_sotto_soglia_non_segnala() -> None:
    r = check_maturity_regression(
        overall_attuale=61.0, overall_precedente=64.0,
        livello_attuale="Fast-tracker", livello_precedente="Fast-tracker",
    )
    assert r == []


def test_calo_medio_di_punteggio() -> None:
    r = check_maturity_regression(
        overall_attuale=62.0, overall_precedente=70.0,
        livello_attuale="Fast-tracker", livello_precedente="Fast-tracker",
    )
    assert _codes(r) == {"regressione_maturita"}
    assert r[0]["livello"] == "medio"
    assert "70" in r[0]["messaggio"] and "62" in r[0]["messaggio"]


def test_calo_forte_e_retrocessione_di_livello() -> None:
    r = check_maturity_regression(
        overall_attuale=35.0, overall_precedente=65.0,
        livello_attuale="Beginner", livello_precedente="Fast-tracker",
    )
    assert _codes(r) == {"regressione_livello", "regressione_maturita"}
    per_codice = {f["codice"]: f for f in r}
    assert per_codice["regressione_livello"]["livello"] == "alto"
    assert per_codice["regressione_maturita"]["livello"] == "alto"  # -30 punti


def test_miglioramento_non_segnala() -> None:
    r = check_maturity_regression(
        overall_attuale=75.0, overall_precedente=55.0,
        livello_attuale="Fast-tracker", livello_precedente="Follower",
    )
    assert r == []


def test_transizione_a_dato_insufficiente() -> None:
    r = check_maturity_regression(
        overall_attuale=None, overall_precedente=62.0,
        livello_attuale="Dato insufficiente", livello_precedente="Fast-tracker",
    )
    assert _codes(r) == {"maturita_non_valutabile"}
    assert r[0]["livello"] == "medio"
    assert "Fast-tracker" in r[0]["messaggio"]


def test_entrambi_insufficienti_non_giudicabile() -> None:
    r = check_maturity_regression(
        overall_attuale=None, overall_precedente=None,
        livello_attuale="Dato insufficiente", livello_precedente="Dato insufficiente",
    )
    assert r == []


def test_uscita_da_dato_insufficiente_non_segnala() -> None:
    # da "insufficiente" a un livello reale: nessun confronto sensato, nessun allarme
    r = check_maturity_regression(
        overall_attuale=45.0, overall_precedente=None,
        livello_attuale="Follower", livello_precedente="Dato insufficiente",
    )
    assert r == []


def test_ordine_livelli_override() -> None:
    r = check_maturity_regression(
        overall_attuale=50.0, overall_precedente=50.0,
        livello_attuale="B", livello_precedente="A",
        livelli_ordine=["B", "A"],  # A è più alto di B
    )
    assert _codes(r) == {"regressione_livello"}
