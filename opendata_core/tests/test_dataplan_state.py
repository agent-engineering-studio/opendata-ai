"""Test della macchina a stati di accompagnamento (#184, D13)."""

from __future__ import annotations

from opendata_core.dataplan import accompaniment_state


def test_zero_dati() -> None:
    s = accompaniment_state(n_dataset=0, overall=None)
    assert s.stato == "zero_dati"
    chiavi = [p.chiave for p in s.percorso]
    # onboarding: diagnosi → policy → catalogo → quick win → brief
    assert chiavi[0] == "diagnosi" and "politica" in chiavi and "piano" in chiavi and "brief" in chiavi
    # baseline assente = zero dati (trattata come tale)
    assert accompaniment_state(n_dataset=0, overall=0).stato == "zero_dati"


def test_pochi_dati_by_count_or_low_score() -> None:
    assert accompaniment_state(n_dataset=3, overall=55).stato == "pochi_dati"   # pochi per numero
    assert accompaniment_state(n_dataset=20, overall=30).stato == "pochi_dati"  # punteggio Beginner
    s = accompaniment_state(n_dataset=3, overall=55)
    assert "piano" in [p.chiave for p in s.percorso]


def test_in_crescita() -> None:
    s = accompaniment_state(n_dataset=12, overall=60)
    assert s.stato == "in_crescita"
    assert "monitoraggio" in [p.chiave for p in s.percorso]


def test_maturo() -> None:
    s = accompaniment_state(n_dataset=40, overall=85)
    assert s.stato == "maturo"
    chiavi = [p.chiave for p in s.percorso]
    assert "benchmark" in chiavi and "monitoraggio" in chiavi


def test_percorso_steps_have_titles_and_action() -> None:
    for n, ov in [(0, None), (3, 30), (12, 60), (40, 90)]:
        s = accompaniment_state(n_dataset=n, overall=ov)
        assert s.etichetta and s.descrizione and s.prossima_azione
        assert s.percorso and all(p.titolo and p.descrizione for p in s.percorso)


def test_monotonic_thresholds() -> None:
    # crescita monotona di stato al crescere di dataset/punteggio
    order = {"zero_dati": 0, "pochi_dati": 1, "in_crescita": 2, "maturo": 3}
    seq = [
        accompaniment_state(n_dataset=0, overall=0),
        accompaniment_state(n_dataset=3, overall=20),
        accompaniment_state(n_dataset=10, overall=60),
        accompaniment_state(n_dataset=30, overall=85),
    ]
    vals = [order[s.stato] for s in seq]
    assert vals == sorted(vals) and vals == [0, 1, 2, 3]
