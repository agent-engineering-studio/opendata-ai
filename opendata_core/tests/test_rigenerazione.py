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


# ── Scoring multicriteria (Fase 2) ─────────────────────────────────────────
from opendata_core.rigenerazione import score_candidato, valuta_aree  # noqa: E402

_PESI = {"centralita": 20, "disponibilita_giuridica": 20, "abbandono": 15,
         "dimensione": 15, "urbanistica": 10, "accesso": 10, "vincoli": 10}


def test_score_normalizza_sui_pesi_valutati() -> None:
    # solo centralità (20) e abbandono (15) valutati, entrambi 1.0 → 100/100
    sc = score_candidato(_PESI, {"centralita": 1.0, "abbandono": 1.0})
    assert sc["punteggio"] == 100 and sc["idoneo"] is True
    # i criteri senza dato finiscono in da_verificare col loro peso
    assert set(sc["da_verificare"]) == {"disponibilita_giuridica", "dimensione",
                                        "urbanistica", "accesso", "vincoli"}


def test_score_nessun_dato_valutabile() -> None:
    sc = score_candidato(_PESI, {k: None for k in _PESI})
    assert sc["punteggio"] is None and sc["idoneo"] is None


def test_score_clamp_e_media_pesata() -> None:
    # centralità 0.5 (20) + dimensione 1.0 (15) → (20*0.5+15*1)/(35)*100 = 71
    sc = score_candidato(_PESI, {"centralita": 0.5, "dimensione": 1.5})  # 1.5 clampato a 1
    assert sc["punteggio"] == round((20 * 0.5 + 15 * 1.0) / 35 * 100)


def test_valuta_aree_ordina_e_calcola() -> None:
    centro = (40.80, 16.92)  # ~Gioia del Colle
    candidati = [
        {"osm_type": "way", "osm_id": 1, "kind": "brownfield", "area_mq": 25000,
         "lat": 40.801, "lon": 16.921, "url": "u1"},   # vicino, grande, dismesso
        {"osm_type": "way", "osm_id": 2, "kind": "parking", "area_mq": 800,
         "lat": 40.86, "lon": 16.99, "url": "u2"},      # lontano, piccolo, parcheggio
    ]
    res = valuta_aree(candidati, centro, target_mq=19500, criteri_pesi=_PESI, vincolo_pct=2.0)
    assert res[0]["osm_id"] == 1  # il brownfield centrale grande vince
    assert res[0]["idoneita"]["punteggio"] >= res[1]["idoneita"]["punteggio"]
    assert "dist_km" in res[0] and res[0]["idoneita"]["da_verificare"]  # proprietà ecc.
