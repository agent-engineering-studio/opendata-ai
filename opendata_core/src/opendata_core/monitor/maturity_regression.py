"""Regressioni di maturità — la scorecard ODM dell'ente è peggiorata? (#103)

Gemello di `quality_regression`, ma a livello di ENTE: confronta gli ultimi due
assessment persistiti (`overall` 0-100 + livello ODM) e segnala i cali. Tre
codici, per gravità del segnale:

- `regressione_livello` (alto) — retrocessione nell'ordine dei livelli ODM
  (es. Fast-tracker → Follower): è il segnale più forte, sempre "alto".
- `regressione_maturita` — calo del punteggio complessivo: sotto i 5 punti non
  si segnala (oscillazioni fisiologiche tra harvest), da 5 "medio", da 15 "alto".
- `maturita_non_valutabile` (medio) — l'ente aveva un livello reale e ora è
  "Dato insufficiente": non è un calo di punteggio ma i dati sono spariti,
  e vale la pena saperlo.

Fail-safe: lista vuota senza assessment precedente o quando ENTRAMBI i lati
sono "Dato insufficiente" (niente da confrontare, nessun numero inventato).
"""

from __future__ import annotations

from typing import Any

from ..maturity.models import DEFAULT_ODM_LEVELS, INSUFFICIENT_LEVEL
from .findings import _finding

_SOGLIA_REGRESSIONE = 5  # punti persi minimi prima di segnalare
_SOGLIA_ALTA = 15  # oltre questa perdita, livello "alto" invece di "medio"


def _ordine_livelli(livelli_ordine: list[str] | None) -> dict[str, int]:
    nomi = livelli_ordine if livelli_ordine is not None else [nome for _, nome in DEFAULT_ODM_LEVELS]
    return {nome: i for i, nome in enumerate(nomi)}


def check_maturity_regression(
    *,
    overall_attuale: float | None,
    overall_precedente: float | None,
    livello_attuale: str | None,
    livello_precedente: str | None,
    livelli_ordine: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Finding di regressione tra gli ultimi due assessment di maturità di un ente.

    Args:
        overall_attuale / overall_precedente: punteggio complessivo 0-100.
        livello_attuale / livello_precedente: livello ODM (o "Dato insufficiente").
        livelli_ordine: override dell'ordine dei livelli (default: ODM 2025).

    Returns:
        Lista di finding (vuota = nessuna regressione giudicabile).
    """
    if livello_precedente is None and overall_precedente is None:
        return []  # primo assessment: niente da confrontare

    findings: list[dict[str, Any]] = []

    # ── transizione a "Dato insufficiente" ──
    attuale_insuff = livello_attuale == INSUFFICIENT_LEVEL
    precedente_insuff = livello_precedente == INSUFFICIENT_LEVEL
    if attuale_insuff and precedente_insuff:
        return []  # non giudicabile su entrambi i lati
    if attuale_insuff:
        # `livello_precedente` può essere None se l'assessment precedente aveva solo
        # un punteggio ma nessun livello: evita di stampare «None» all'utente.
        riferimento = f"era valutato «{livello_precedente}»" if livello_precedente else "aveva una valutazione"
        findings.append(_finding(
            "medio", "maturita_non_valutabile",
            f"L'ente {riferimento} ma l'ultima valutazione non ha "
            "dati sufficienti per un giudizio: verifica che il portale e i dataset siano "
            "ancora raggiungibili.",
        ))
        return findings  # i punteggi con dato insufficiente non sono confrontabili

    # ── retrocessione di livello ODM ──
    ordine = _ordine_livelli(livelli_ordine)
    if (
        not precedente_insuff
        and livello_attuale in ordine
        and livello_precedente in ordine
        and ordine[livello_attuale] < ordine[livello_precedente]
    ):
        findings.append(_finding(
            "alto", "regressione_livello",
            f"Livello di maturità sceso da «{livello_precedente}» a «{livello_attuale}».",
        ))

    # ── calo del punteggio complessivo ──
    if overall_attuale is not None and overall_precedente is not None and not precedente_insuff:
        delta = overall_attuale - overall_precedente
        if delta <= -_SOGLIA_REGRESSIONE:
            livello = "alto" if delta <= -_SOGLIA_ALTA else "medio"
            findings.append(_finding(
                livello, "regressione_maturita",
                f"Punteggio di maturità sceso da {round(overall_precedente, 1)} a "
                f"{round(overall_attuale, 1)} ({round(delta, 1)} punti).",
            ))

    return findings
