"""Motore generico di dimensionamento (`valuta_pattern`) — pattern di rigenerazione.

Verifica i quattro tipi di formula (lineare, per_mille, classi, soglia) su un
catalogo di esempio. Il catalogo reale vive in opendata_backend/config_data e
viene iniettato dal backend: qui il motore è puro e riceve i pattern come input.
"""

from __future__ import annotations

from opendata_core.rigenerazione import valuta_pattern

_CATALOG = [
    {
        "id": "aree_mercatali",
        "tema": "Mercato",
        "norma": "D.M. 1444/1968",
        "formula": {
            "tipo": "classi",
            "unita": "mq",
            "derivati": [{"nome": "posteggi_indicativi", "fattore": 0.0171875}],
            "classi": [
                {"max_ab": 2000, "coeff": None, "valore_soglia": 1750, "assetto": "soglia"},
                {"max_ab": 10000, "coeff": 1.0, "assetto": "polo unico"},
                {"max_ab": None, "coeff": 0.7, "assetto": "rete di poli"},
            ],
        },
    },
    {"id": "impianti_sportivi", "tema": "Sport", "norma": "D.M. 1444/1968",
     "formula": {"tipo": "lineare", "unita": "mq", "coeff": 4}},
    {"id": "rete_ciclabile", "tema": "Ciclabili", "norma": "PUMS",
     "formula": {"tipo": "per_mille", "unita": "km", "coeff": 1.5, "decimali": 1}},
    {"id": "traffico", "tema": "Traffico", "norma": "PUMS",
     "formula": {"tipo": "soglia", "soglia_ab": 100000,
                 "se_sopra": "PUMS obbligatorio", "se_sotto": "PUMS raccomandato"}},
]


def _by_id(res: list[dict], pid: str) -> dict:
    return next(r for r in res if r["id"] == pid)


def test_gioia_del_colle_classe_e() -> None:
    res = valuta_pattern(27889, _CATALOG)
    m = _by_id(res, "aree_mercatali")
    assert m["coeff"] == 0.7 and m["target"] == 19500  # 27889×0,7 ≈ 19.500
    assert m["posteggi_indicativi"] == round(19500 * 0.0171875)  # ≈ 335
    assert "rete di poli" in m["assetto"]
    assert _by_id(res, "impianti_sportivi")["target"] == 111600  # 27889×4
    assert _by_id(res, "rete_ciclabile")["target"] == 41.8  # 27889/1000×1,5
    assert _by_id(res, "traffico")["target"] == "PUMS raccomandato"  # < 100k


def test_soglia_piccolo_comune() -> None:
    m = _by_id(valuta_pattern(1800, _CATALOG), "aree_mercatali")
    assert m["coeff"] is None and m["target"] == 1750


def test_pums_obbligatorio_grande_citta() -> None:
    t = _by_id(valuta_pattern(120000, _CATALOG), "traffico")
    assert t["soglia_superata"] is True and t["target"] == "PUMS obbligatorio"


def test_tipo_sconosciuto_saltato() -> None:
    res = valuta_pattern(5000, [{"id": "x", "formula": {"tipo": "boh"}}])
    assert res == []


def test_metadati_passati_attraverso() -> None:
    m = _by_id(valuta_pattern(7000, _CATALOG), "aree_mercatali")
    assert m["norma"] == "D.M. 1444/1968" and m["target"] == 7000  # classe 5-10k, k=1.0
