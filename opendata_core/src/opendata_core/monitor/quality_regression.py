"""Controllo di regressione qualità — il punteggio è sceso rispetto al run precedente?

`check_quality_regression` confronta il punteggio di `profile_csv`/`profile_geojson`
(0-100) tra due run consecutivi dello stesso target. Una soglia (10 punti) evita
di segnalare oscillazioni minime dovute a piccole variazioni del file.
"""

from __future__ import annotations

from typing import Any

from .findings import _finding

_SOGLIA_REGRESSIONE = 10  # punti persi minimi prima di segnalare
_SOGLIA_ALTA = 30  # oltre questa perdita, livello "alto" invece di "medio"


def check_quality_regression(
    punteggio_attuale: int | float,
    punteggio_precedente: int | float | None,
) -> dict[str, Any] | None:
    """Finding se il punteggio è sceso oltre soglia, `None` se non c'è un run precedente o è stabile/migliorato."""
    if punteggio_precedente is None:
        return None
    delta = punteggio_attuale - punteggio_precedente
    if delta > -_SOGLIA_REGRESSIONE:
        return None
    livello = "alto" if delta <= -_SOGLIA_ALTA else "medio"
    return _finding(
        livello, "regressione_qualita",
        f"Punteggio qualità sceso da {punteggio_precedente} a {punteggio_attuale} "
        f"({round(delta)} punti).",
    )
