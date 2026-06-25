"""Dimensionamento parametrico (rigenerazione) — motore deterministico.

Verifica le formule e le classi dimensionali contro i valori del framework
(D.M. 1444/1968, CONI, PUMS). Nessuna fonte live: tutto è funzione della sola
popolazione.
"""

from __future__ import annotations

from opendata_core.rigenerazione import DOMINI, dimensiona


def test_domini_presenti() -> None:
    d = dimensiona(27889)
    assert d["popolazione"] == 27889
    for k in DOMINI:
        assert k in d


def test_gioia_del_colle_classe_e() -> None:
    """27.889 ab → classe >20k: k=0,7 (rete di poli), sport 9/4 mq/ab, ciclabili 1,5 km/1000."""
    d = dimensiona(27889)
    m = d["aree_mercatali"]
    assert m["k_mq_ab"] == 0.7
    assert m["superficie_target_mq"] == 19500  # 27889×0,7 ≈ 19.500 (arrot. 100)
    assert m["posteggi_indicativi"] == round(19500 * 0.55 / 32)  # ≈ 335
    assert "rete di poli" in m["assetto"]

    sp = d["sport"]
    assert sp["verde_gioco_sport_mq"] == 251000  # 27889×9 ≈ 251.000
    assert sp["impianti_sportivi_mq"] == 111600  # 27889×4 ≈ 111.600

    assert d["ciclabili"]["rete_target_km"] == 41.8  # 27889/1000×1,5
    assert d["traffico"]["pums_obbligatorio"] is False  # < 100k


def test_soglia_piccolo_comune() -> None:
    """Sotto i 2.000 ab: soglia funzionale (k=None), non Pop×k."""
    m = dimensiona(1800)["aree_mercatali"]
    assert m["k_mq_ab"] is None
    assert m["superficie_target_mq"] == 1750


def test_pums_obbligatorio_grande_citta() -> None:
    assert dimensiona(120000)["traffico"]["pums_obbligatorio"] is True


def test_classi_coefficiente_mercatali() -> None:
    """k decrescente per classe dimensionale crescente."""
    assert dimensiona(3000)["aree_mercatali"]["k_mq_ab"] == 1.1
    assert dimensiona(7000)["aree_mercatali"]["k_mq_ab"] == 1.0
    assert dimensiona(15000)["aree_mercatali"]["k_mq_ab"] == 0.85
    assert dimensiona(25000)["aree_mercatali"]["k_mq_ab"] == 0.7


def test_norma_citata_in_ogni_dominio() -> None:
    d = dimensiona(10000)
    for k in DOMINI:
        assert d[k].get("norma"), f"manca la norma per {k}"
