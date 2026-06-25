"""Dimensionamento parametrico — i quattro domini di rigenerazione urbana.

Tutto deriva dalla popolazione residente con coefficienti e classi dimensionali
codificati qui (nessuna fonte live). I valori sono TARGET di programmazione
(obiettivi di dotazione), non misure osservate: vanno confrontati con l'esistente
per stimare il gap.

Riferimenti: D.M. 1444/1968 (standard urbanistici), norme CONI-CIS (impianti
sportivi), PUMS / riferimento europeo per la rete ciclabile, Reg. UE 2024/1679
(TEN-T) per l'obbligo di PUMS sui nodi urbani.
"""

from __future__ import annotations

from typing import Any

# D.M. 1444/1968: 9 mq/ab a verde-gioco-sport (parte dei 18 mq/ab complessivi);
# di questi ~4 mq/ab riconducibili a impianti sportivi veri e propri.
_SPORT_MQ_AB = 9.0
_SPORT_IMPIANTI_MQ_AB = 4.0
# PUMS / riferimento europeo: ~1,5 km di rete ciclabile ogni 1.000 abitanti.
_CICLABILI_KM_PER_1000 = 1.5
# PUMS obbligatorio sopra i 100.000 ab (Reg. UE 2024/1679 estende l'obbligo ai
# nodi urbani entro il 2027); sotto è raccomandato in forma semplificata.
_PUMS_SOGLIA_OBBLIGO = 100_000

DOMINI = ("aree_mercatali", "sport", "ciclabili", "traffico")


def _round100(x: float) -> int:
    """Arrotonda a 100 (i target sono indicativi, non spuri al singolo mq)."""
    return int(round(x / 100.0) * 100)


def _mercatali(pop: int) -> dict[str, Any]:
    """Area polifunzionale mercato/eventi/partecipazione: superficie e posteggi.

    `Superficie = Pop × k`, con k decrescente per classe (economia di scala e
    saturazione della domanda); sotto i 2.000 ab vale una soglia minima funzionale.
    Posteggi ≈ Superficie × 0,55 ÷ 32 mq (modulo stallo/stand tipo).
    """
    if pop < 2000:
        k: float | None = None
        assetto = "polo unico minimo (soglia funzionale)"
        superficie = 1750  # soglia 1.500–2.000 mq
    elif pop < 5000:
        k, assetto = 1.1, "polo unico"
        superficie = _round100(pop * k)
    elif pop < 10000:
        k, assetto = 1.0, "polo unico"
        superficie = _round100(pop * k)
    elif pop < 20000:
        k, assetto = 0.85, "1–2 poli"
        superficie = _round100(pop * k)
    else:
        k, assetto = 0.7, "rete di poli (decentramento)"
        superficie = _round100(pop * k)
    return {
        "superficie_target_mq": superficie,
        "k_mq_ab": k,
        "posteggi_indicativi": int(round(superficie * 0.55 / 32)),
        "assetto": assetto,
        "norma": "D.M. 1444/1968 (attrezzature di interesse comune) + modello aree mercatali polifunzionali",
    }


def _sport(pop: int) -> dict[str, Any]:
    """Verde-gioco-sport e, al suo interno, impianti sportivi (mq target)."""
    if pop < 2000:
        dotazione = "campo polivalente + area gioco"
    elif pop < 5000:
        dotazione = "palestra + campo + polivalenti"
    elif pop < 10000:
        dotazione = "centro sportivo: calcio + palestra + polivalenti"
    elif pop < 20000:
        dotazione = "polo sportivo + piscina"
    else:
        dotazione = "più centri di quartiere + impianto natatorio"
    return {
        "verde_gioco_sport_mq": _round100(pop * _SPORT_MQ_AB),
        "impianti_sportivi_mq": _round100(pop * _SPORT_IMPIANTI_MQ_AB),
        "dotazione_tipo": dotazione,
        "norma": "D.M. 1444/1968 (9 mq/ab verde-gioco-sport) + norme CONI-CIS per i singoli impianti",
    }


def _ciclabili(pop: int) -> dict[str, Any]:
    """Rete ciclabile/mobilità dolce: km target (sistema continuo, non tratti isolati)."""
    if pop < 5000:
        assetto = "collegamenti scuola–centro–sport"
    elif pop < 10000:
        assetto = "dorsale + anello urbano + zone 30"
    elif pop < 20000:
        assetto = "rete a maglia + bike sharing"
    else:
        assetto = "rete strutturata + intermodalità con TPL"
    return {
        "rete_target_km": round(pop / 1000.0 * _CICLABILI_KM_PER_1000, 1),
        "assetto": assetto,
        "norma": "riferimento PUMS/europeo ≈ 1,5 km di rete ogni 1.000 ab",
    }


def _traffico(pop: int) -> dict[str, Any]:
    """Mobilità sostenibile: strumento di piano + leve di intervento."""
    obbligo = pop >= _PUMS_SOGLIA_OBBLIGO
    return {
        "pums_obbligatorio": obbligo,
        "strumento": (
            "PUMS obbligatorio"
            if obbligo
            else "PUMS raccomandato (forma semplificata: Piano del traffico / Biciplan)"
        ),
        "leve": "zone 30, ZTL/aree pedonali, sosta di scambio, riequilibrio modale, ITS",
        "norma": "PUMS; Reg. UE 2024/1679 (TEN-T) — nodi urbani entro il 2027",
    }


def dimensiona(popolazione: int) -> dict[str, Any]:
    """Target normativi di dotazione per i 4 domini di rigenerazione.

    Args:
        popolazione: popolazione residente del comune.

    Returns:
        dict con `popolazione` + una chiave per dominio (vedi DOMINI), ciascuna
        con i target e la norma di riferimento. I valori sono OBIETTIVI di
        programmazione, da confrontare con la dotazione osservata.
    """
    pop = max(0, int(popolazione))
    return {
        "popolazione": pop,
        "aree_mercatali": _mercatali(pop),
        "sport": _sport(pop),
        "ciclabili": _ciclabili(pop),
        "traffico": _traffico(pop),
    }
