"""Lookup sull'anagrafica comuni (popolazione) — usata per la strategia
"città grande": sopra una soglia l'analisi passa in modalità macro (aggregati
+ top-N) invece di enumerare migliaia di progetti.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ComuneAnagrafica


async def get_popolazione(session: AsyncSession, cod_comune: str) -> int | None:
    """Popolazione del comune dall'anagrafica locale, o None se assente.

    None quando l'anagrafica non è stata sincronizzata (`make comuni-sync`) o
    il comune non c'è: il chiamante tratta None come "non grande".
    """
    cod = (cod_comune or "").strip().zfill(6)
    row = await session.scalar(
        select(ComuneAnagrafica.popolazione).where(ComuneAnagrafica.cod_comune == cod)
    )
    return int(row) if row is not None else None
