"""Registro documenti PA ingeriti nel KG (F2) — backing del file manager."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Documento


async def create(
    session: AsyncSession,
    *,
    cod_comune: str,
    filename: str,
    kg_namespace: str,
    sha256: str | None,
    mime_type: str | None,
    caricato_da: str | None,
    stato: str = "in_ingest",
) -> Documento:
    doc = Documento(
        cod_comune=cod_comune.strip(),
        filename=filename,
        kg_namespace=kg_namespace,
        sha256=sha256,
        mime_type=mime_type,
        caricato_da=caricato_da,
        stato=stato,
    )
    session.add(doc)
    await session.flush()
    return doc


async def list_by_comune(session: AsyncSession, cod_comune: str) -> list[Documento]:
    rows = await session.scalars(
        select(Documento)
        .where(Documento.cod_comune == cod_comune.strip())
        .order_by(Documento.caricato_il.desc())
    )
    return list(rows)


async def get(session: AsyncSession, doc_id: int) -> Documento | None:
    return await session.get(Documento, doc_id)


async def delete(session: AsyncSession, doc: Documento) -> None:
    await session.delete(doc)
