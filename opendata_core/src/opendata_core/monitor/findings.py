"""Helper condiviso per costruire un finding di monitoraggio.

Stessa forma (`livello`/`codice`/`messaggio`) dei finding del Data Quality Lab
(`opendata_core.quality.profile._finding`), per coerenza in tutta la UI.
"""

from __future__ import annotations

from typing import Any


def _finding(livello: str, codice: str, messaggio: str) -> dict[str, Any]:
    return {"livello": livello, "codice": codice, "messaggio": messaggio}
