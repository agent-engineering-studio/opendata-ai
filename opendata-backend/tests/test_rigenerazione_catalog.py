"""Catalogo pattern di rigenerazione (config_data/rigenerazione_patterns.yaml).

Verifica che il catalogo REALE carichi e che il motore puro
`opendata_core.rigenerazione.valuta_pattern` produca i target attesi — chiude il
giro loader YAML → engine, che il test puro in opendata_core (catalogo inline)
non copre.
"""

from __future__ import annotations

from opendata_backend.config_files import rigenerazione_patterns
from opendata_core.rigenerazione import valuta_pattern


def _by_id(res: list[dict], pid: str) -> dict | None:
    return next((r for r in res if r["id"] == pid), None)


def test_catalogo_si_carica() -> None:
    cat = rigenerazione_patterns()
    assert isinstance(cat, list) and cat, "catalogo vuoto o non caricato"
    ids = {p["id"] for p in cat}
    # I domini attesi dei due modelli PDF + il pattern nuovo (parcheggi).
    assert {"aree_mercatali", "impianti_sportivi", "rete_ciclabile", "traffico_mobilita"} <= ids


def test_target_gioia_del_colle() -> None:
    """27.889 ab (Gioia del Colle, pilota): i numeri del framework parametrico."""
    res = valuta_pattern(27889, rigenerazione_patterns())
    m = _by_id(res, "aree_mercatali")
    assert m and m["target"] == 19500 and m["posteggi_indicativi"] == 335
    assert _by_id(res, "verde_gioco_sport")["target"] == 251000
    assert _by_id(res, "impianti_sportivi")["target"] == 111600
    assert _by_id(res, "rete_ciclabile")["target"] == 41.8
    assert _by_id(res, "parcheggi_pubblici")["target"] == 69700  # 27889×2,5 ≈ 69.700
    assert _by_id(res, "traffico_mobilita")["target"].startswith("PUMS raccomandato")


def test_ogni_pattern_cita_norma_e_sdg() -> None:
    for r in valuta_pattern(10000, rigenerazione_patterns()):
        assert r.get("norma"), f"manca la norma per {r['id']}"
        assert r.get("sdg", "").startswith("SDG"), f"manca/SDG malformato per {r['id']}"
