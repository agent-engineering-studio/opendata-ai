"""Cache delle analisi /programma (F1): replay esatto della scheda senza
rigenerare il fan-out.

La chiave include `knowledge_version` (per comune) e `prompt_version`: bumpando
la versione conoscenza (F2, su upload/delete documenti) o cambiando i prompt,
le voci vecchie semplicemente non vengono più trovate (e scadono per TTL).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ComuneKnowledge, ProgrammaCache


def compute_cache_key(
    *,
    cod_comune: str,
    tema: str | None,
    cicli: list[str] | None,
    modalita: str,
    knowledge_version: int,
    prompt_version: str,
) -> str:
    """Chiave deterministica dell'analisi. Tema/cicli normalizzati così
    l'ordine o il maiuscolo non cambiano l'hit."""
    cicli_norm = ",".join(sorted(c.strip() for c in (cicli or []) if c.strip()))
    raw = "|".join(
        [
            (cod_comune or "").strip(),
            (tema or "").strip().lower(),
            cicli_norm,
            (modalita or "").strip().lower(),
            f"kv={knowledge_version}",
            f"pv={prompt_version}",
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


async def get_knowledge_version(session: AsyncSession, cod_comune: str) -> int:
    """Versione conoscenza del comune (0 se mai toccata)."""
    v = await session.scalar(
        select(ComuneKnowledge.version).where(ComuneKnowledge.cod_comune == cod_comune.strip())
    )
    return int(v) if v is not None else 0


async def get_fresh(
    session: AsyncSession, cache_key: str, *, now: datetime
) -> ProgrammaCache | None:
    """Riga di cache non scaduta per la chiave, o None."""
    row = await session.scalar(
        select(ProgrammaCache).where(ProgrammaCache.cache_key == cache_key)
    )
    if row is None:
        return None
    # SQLite (test) restituisce datetime naive, Postgres aware: normalizza a
    # UTC prima del confronto per non far esplodere il "<=".
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        return None
    return row


async def upsert(
    session: AsyncSession,
    *,
    cache_key: str,
    cod_comune: str,
    tema: str | None,
    modalita: str,
    knowledge_version: int,
    prompt_version: str,
    scheda_json: str,
    generato_il: datetime,
    expires_at: datetime,
) -> None:
    """Inserisce o aggiorna la scheda in cache per la chiave (portabile
    Postgres/SQLite: select + update/insert, niente upsert dialettale)."""
    row = await session.scalar(
        select(ProgrammaCache).where(ProgrammaCache.cache_key == cache_key)
    )
    if row is None:
        session.add(
            ProgrammaCache(
                cache_key=cache_key,
                cod_comune=cod_comune.strip(),
                tema=(tema or None),
                modalita=modalita,
                knowledge_version=knowledge_version,
                prompt_version=prompt_version,
                scheda_json=scheda_json,
                generato_il=generato_il,
                expires_at=expires_at,
            )
        )
    else:
        row.scheda_json = scheda_json
        row.knowledge_version = knowledge_version
        row.prompt_version = prompt_version
        row.generato_il = generato_il
        row.expires_at = expires_at
