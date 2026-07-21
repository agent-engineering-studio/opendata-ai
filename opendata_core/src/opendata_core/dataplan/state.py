"""Accompagnamento attivo: macchina a stati zero→maturo (#184, D13 di #170).

Motore **puro e deterministico**: dallo stato dell'ente (baseline `assess_entity`
— numero di dataset + punteggio ODM) ricava lo **stato di accompagnamento** e il
**percorso ente-specifico** da proporre. Non una guida passiva: ogni stato mappa
su un insieme ordinato di passi/artefatti del Copilota.

Le transizioni sono alimentate dall'anello valore⇄maturità (Fase 5): i dataset
mancanti sono *domanda di riuso non soddisfatta* → resi azionabili nel percorso.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Stato = Literal["zero_dati", "pochi_dati", "in_crescita", "maturo"]

# soglie (allineate all'ODM 2025 usato in maturity)
_SOGLIA_POCHI = 5      # < 5 dataset = ancora "pochi dati"
_OVERALL_CRESCITA = 40  # Follower
_OVERALL_MATURO = 80    # Trend-setter


class PercorsoStep(BaseModel):
    """Un passo del percorso proposto (mappa su un artefatto/endpoint del Copilota)."""

    chiave: str
    titolo: str
    descrizione: str
    endpoint: str | None = None  # es. "/dataplan/{istat}/piano"; None se azione esterna


class AccompanimentState(BaseModel):
    """Stato di accompagnamento + percorso ente-specifico."""

    stato: Stato
    etichetta: str
    descrizione: str
    prossima_azione: str
    percorso: list[PercorsoStep]


# passi riusabili (endpoint del backend dataplan)
def _step(chiave: str, titolo: str, descrizione: str, endpoint: str | None = None) -> PercorsoStep:
    return PercorsoStep(chiave=chiave, titolo=titolo, descrizione=descrizione, endpoint=endpoint)


_S_DIAGNOSI = _step("diagnosi", "Diagnosi a costo zero",
                    "Cosa è già aperto (portale + adempimenti nazionali).",
                    "/dataplan/{istat}/diagnosi")
_S_POLITICA = _step("politica", "Bozza di Politica Open Data",
                    "Atto di indirizzo generato, da adottare.", "/dataplan/{istat}/politica")
_S_INVENTARIO = _step("inventario", "Inventario del potenziale",
                      "Quali dati puoi/devi aprire.", "/dataplan/{istat}/inventario")
_S_PIANO = _step("piano", "Piano prioritizzato (quick win)",
                 "Cosa aprire prima, per valore/sforzo.", "/dataplan/{istat}/piano")
_S_BRIEF = _step("brief", "Export brief per l'ufficio",
                 "Istruzione operativa per pubblicare un dataset.", "/dataplan/{istat}/brief")
_S_MONITOR = _step("monitoraggio", "Monitoraggio freshness/qualità",
                   "I dataset pubblicati restano vivi (avvisi automatici).", None)
_S_BENCHMARK = _step("benchmark", "Benchmark tra enti + copertura HVD",
                     "Confronto con enti simili e paniere High-Value Dataset.",
                     "/maturity/entities/{entity}")


def accompaniment_state(*, n_dataset: int, overall: float | None) -> AccompanimentState:
    """Determina stato + percorso dal baseline dell'ente. Deterministico.

    ``n_dataset`` = dataset già pubblicati sul portale; ``overall`` = punteggio ODM
    (None se baseline non calcolata → trattato come zero dati).
    """
    ov = overall or 0.0
    if n_dataset <= 0:
        return AccompanimentState(
            stato="zero_dati",
            etichetta="Zero dati",
            descrizione="L'ente non pubblica ancora open data (o baseline non calcolata).",
            prossima_azione="Parti dalla diagnosi e dalla bozza di Politica, poi apri il lotto quick win.",
            percorso=[_S_DIAGNOSI, _S_POLITICA, _S_INVENTARIO, _S_PIANO, _S_BRIEF],
        )
    if n_dataset < _SOGLIA_POCHI or ov < _OVERALL_CRESCITA:
        return AccompanimentState(
            stato="pochi_dati",
            etichetta="Pochi dati",
            descrizione="Pubblicazione episodica: mappa i gap rispetto a HVD e domanda di riuso.",
            prossima_azione="Guarda il piano prioritizzato e genera i brief sui dataset mancanti.",
            percorso=[_S_DIAGNOSI, _S_PIANO, _S_BRIEF, _S_POLITICA],
        )
    if ov < _OVERALL_MATURO:
        return AccompanimentState(
            stato="in_crescita",
            etichetta="In crescita",
            descrizione="Buona base: consolida qualità/freschezza e aggiungi dataset dalla domanda.",
            prossima_azione="Attiva il monitoraggio e usa il piano per i prossimi dataset ad alto valore.",
            percorso=[_S_MONITOR, _S_PIANO, _S_BRIEF],
        )
    return AccompanimentState(
        stato="maturo",
        etichetta="Maturo",
        descrizione="Ente di riferimento: mantenimento, benchmark e copertura HVD completa.",
        prossima_azione="Mantieni i dataset vivi e confrontati con gli enti simili.",
        percorso=[_S_MONITOR, _S_BENCHMARK, _S_PIANO],
    )
