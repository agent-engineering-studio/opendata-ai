"""Scoring multicriteria di idoneità di un'area/corridoio candidato (0–100).

Matrice del framework "Territorio in dati": ogni criterio ha un peso (dal catalogo
pattern, campo `criteri_pesi`) e un valore normalizzato 0..1 calcolabile dai dati
(OSM/ISPRA) oppure `None` se il dato non è disponibile dalle fonti aperte
(es. proprietà catastale / destinazione di PUG → "da verificare").

Il punteggio è la somma pesata dei criteri VALUTABILI, riportata su 100 sui soli
pesi valutati; i criteri non valutabili sono elencati a parte col loro peso, così
il lettore sa quanta parte della valutazione resta da verificare (onestà: niente
punteggio gonfiato spacciando per certo ciò che non lo è). PURO, nessuna fonte live.
"""

from __future__ import annotations

import math
from typing import Any

# Soglia di idoneità consigliata dal framework (matrice ≥ 60/100).
SOGLIA_IDONEITA = 60

# Quanto un tipo OSM di area indica abbandono/sottoutilizzo (criterio "abbandono").
_ABBANDONO_SCORE = {
    "brownfield": 1.0,   # area dismessa / da bonificare
    "ruins": 1.0,
    "railway": 0.9,      # ex sedime ferroviario dismesso
    "greenfield": 0.7,   # libera edificabile
    "square": 0.4,       # piazza/slargo (sottoutilizzo, non abbandono)
    "parking": 0.4,      # parcheggio riqualificabile
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, a**0.5))


def score_candidato(
    criteri_pesi: dict[str, float],
    valori: dict[str, float | None],
) -> dict[str, Any]:
    """Calcola il punteggio di idoneità di un candidato.

    Args:
        criteri_pesi: pesi della matrice (es. {"centralita": 20, ...}); somma ~100.
        valori: per ogni criterio un valore 0..1 (quanto soddisfa) o None se il
            dato non è disponibile dalle fonti aperte.

    Returns:
        dict con `punteggio` (0–100 sui pesi valutati, None se nulla è valutabile),
        `idoneo` (≥ soglia), `peso_valutato`, `da_verificare` (criteri senza dato
        col relativo peso) e `valutati` (dettaglio dei criteri usati).
    """
    valutati = {
        k: max(0.0, min(1.0, float(v)))
        for k, v in valori.items()
        if v is not None and criteri_pesi.get(k)
    }
    da_verificare = {
        k: w for k, w in criteri_pesi.items() if w and valori.get(k) is None
    }
    peso_valutato = sum(criteri_pesi[k] for k in valutati)
    if peso_valutato <= 0:
        return {
            "punteggio": None,
            "idoneo": None,
            "peso_valutato": 0,
            "da_verificare": da_verificare,
            "valutati": {},
        }
    raw = sum(criteri_pesi[k] * v for k, v in valutati.items())
    punteggio = round(raw / peso_valutato * 100)
    return {
        "punteggio": punteggio,
        "idoneo": punteggio >= SOGLIA_IDONEITA,
        "peso_valutato": int(peso_valutato),
        "da_verificare": da_verificare,
        "valutati": {k: round(v, 2) for k, v in valutati.items()},
    }


def valuta_aree(
    candidati: list[dict[str, Any]],
    centro: tuple[float, float],
    target_mq: float | None,
    criteri_pesi: dict[str, float],
    *,
    vincolo_pct: float | None = None,
) -> list[dict[str, Any]]:
    """Valuta e ordina le aree candidate con la matrice multicriteria.

    Calcola i criteri computabili dalle fonti aperte (centralità dalla distanza dal
    centro, dimensione vs target del pattern, abbandono dal tipo OSM, vincoli da
    ISPRA se passati) e lascia a `None` (→ "da verificare") quelli non desumibili da
    open data (proprietà catastale, compatibilità urbanistica, accesso/sosta).

    Args:
        candidati: output di `osm.client.overpass_candidate_areas` (lat, lon, area_mq, kind…).
        centro: (lat, lon) del centro del comune (per la centralità).
        target_mq: superficie target del pattern (per la dimensione); None la salta.
        criteri_pesi: pesi della matrice del pattern.
        vincolo_pct: % di territorio comunale a pericolosità (ISPRA), se nota.

    Returns:
        i candidati arricchiti con `dist_km` e `idoneita` (vedi `score_candidato`),
        ordinati per punteggio decrescente.
    """
    clat, clon = centro
    vincolo_val = (
        None if vincolo_pct is None else max(0.0, 1.0 - min(1.0, float(vincolo_pct) / 100.0 * 3.0))
    )
    out: list[dict[str, Any]] = []
    for c in candidati:
        dist_km = _haversine_km(clat, clon, c["lat"], c["lon"])
        valori: dict[str, float | None] = {
            "centralita": max(0.0, 1.0 - dist_km / 3.0),
            "dimensione": (min(1.0, c["area_mq"] / target_mq) if target_mq else None),
            "abbandono": _ABBANDONO_SCORE.get(c.get("kind", ""), 0.6),
            "accesso": None,                  # sosta/carico-scarico → da verificare
            "disponibilita_giuridica": None,  # proprietà/PUG → da verificare (no open data)
            "urbanistica": None,              # destinazione di piano → da verificare
            "vincoli": vincolo_val,
        }
        out.append({**c, "dist_km": round(dist_km, 2), "idoneita": score_candidato(criteri_pesi, valori)})
    out.sort(key=lambda d: (d["idoneita"].get("punteggio") or 0), reverse=True)
    return out
