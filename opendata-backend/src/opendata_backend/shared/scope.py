"""Enforcement dello scope regionale sugli endpoint territoriali (issue #191, F3).

Guardia async condivisa da `/territory/*`, `/maturity/*` (e ovunque un endpoint
riceva un `istat_code`/comune): un comune fuori dalla regione configurata
(`REGION`, vedi F1) → **HTTP 422**.

Il confronto è basato sul campo **autorevole** `ComuneAnagrafica.cod_regione`
(`db/models.py`, indicizzato) quando l'anagrafica copre il comune; altrimenti
degrada in modo deterministico al prefisso provincia (`check_territorio_scope`,
con `province_scope` derivato da `REGION` o dal legacy `TERRITORIO_PROVINCE`).
No-op quando nessuno scope è configurato (dev senza limiti) → retro-compatibile.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, check_territorio_scope, region_config
from ..db.models import ComuneAnagrafica


async def _lookup_cod_regione(session: AsyncSession, cod_comune: str) -> str | None:
    """`cod_regione` autorevole del comune dall'anagrafica, o None se assente."""
    candidates = {cod_comune, cod_comune.zfill(6)}
    row = await session.scalar(
        select(ComuneAnagrafica.cod_regione).where(
            ComuneAnagrafica.cod_comune.in_(candidates)
        )
    )
    return str(row) if row else None


async def enforce_region_scope(
    session: AsyncSession | None,
    cod_comune: str | None,
    settings: Settings,
) -> None:
    """Rifiuta (HTTP 422) un comune fuori dalla regione/ambito configurato.

    Ordine di valutazione:
      1. `REGION` impostato + anagrafica disponibile → confronto autorevole su
         `cod_regione` (match esatto = ammesso, mismatch = 422).
      2. Altrimenti fallback al prefisso provincia (`check_territorio_scope`),
         che copre anche `REGION` vuoto con `TERRITORIO_PROVINCE`.
      3. Nessuno scope configurato → no-op.
    """
    if not cod_comune:
        return
    cod_comune = str(cod_comune).strip()
    if not cod_comune:
        return

    reg = region_config(settings)
    if reg is not None and session is not None:
        target = (settings.region_istat or "").strip().zfill(2)
        cod_regione = await _lookup_cod_regione(session, cod_comune)
        if cod_regione is not None:
            if cod_regione.zfill(2) != target:
                nome = reg.get("nome") or target
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Il comune {cod_comune} è fuori dalla regione configurata "
                        f"({nome}, cod_regione={target}): questo deployment è "
                        f"limitato a una sola regione."
                    ),
                )
            return

    # Fallback deterministico (anagrafica assente o REGION vuoto): prefisso provincia.
    try:
        check_territorio_scope(cod_comune, settings)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
