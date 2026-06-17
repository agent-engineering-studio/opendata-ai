"""Reuse/impact score di un dataset da dati reali della piattaforma.

Segnali: preferiti (favorites) + classificazioni richieste (classifications). La
history non è legata a un dataset_id puntuale, quindi non concorre. Normalizzato 0–100.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Classification, Favorite


async def reuse_score(session: AsyncSession, *, source: str, dataset_id: str) -> float:
    """Reuse score 0–100 per (source, dataset_id) dai segnali di piattaforma."""
    fav = (
        await session.execute(
            select(func.count()).select_from(Favorite).where(
                Favorite.source == source, Favorite.dataset_id == dataset_id
            )
        )
    ).scalar_one()
    cls = (
        await session.execute(
            select(func.count()).select_from(Classification).where(
                Classification.source == source, Classification.dataset_id == dataset_id
            )
        )
    ).scalar_one()
    return float(min(100, int(fav) * 25 + int(cls) * 10))
