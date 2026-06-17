"""Persistenza community: membri/ruoli, thread, post (moderazione).

GDPR: si memorizzano dati personali MINIMI (id utente Clerk opaco + display name
opzionale). Nessun contenuto sensibile richiesto; i post sono pubblici per comune.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..territory_models import CommunityMember, CommunityPost, CommunityThread

ROLES = ("cittadino", "moderatore", "amministratore")
_MOD_ROLES = {"moderatore", "amministratore"}


async def get_role(session: AsyncSession, *, clerk_user_id: str, istat_code: str) -> str:
    row = (
        await session.execute(
            select(CommunityMember).where(
                CommunityMember.clerk_user_id == clerk_user_id,
                CommunityMember.istat_code == istat_code,
            )
        )
    ).scalar_one_or_none()
    return row.role if row else "cittadino"


async def set_role(
    session: AsyncSession, *, clerk_user_id: str, istat_code: str, role: str,
    display_name: str | None = None,
) -> CommunityMember:
    if role not in ROLES:
        raise ValueError(f"ruolo non valido: {role}")
    row = (
        await session.execute(
            select(CommunityMember).where(
                CommunityMember.clerk_user_id == clerk_user_id,
                CommunityMember.istat_code == istat_code,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = CommunityMember(clerk_user_id=clerk_user_id, istat_code=istat_code, role=role,
                              display_name=display_name)
        session.add(row)
    else:
        row.role = role
        if display_name:
            row.display_name = display_name
    await session.flush()
    return row


def is_moderator(role: str) -> bool:
    return role in _MOD_ROLES


async def create_thread(
    session: AsyncSession, *, istat_code: str, topic_type: str, title: str,
    topic_ref: str | None = None, created_by: str | None = None,
) -> CommunityThread:
    row = CommunityThread(istat_code=istat_code, topic_type=topic_type, topic_ref=topic_ref,
                          title=title, created_by=created_by)
    session.add(row)
    await session.flush()
    return row


async def list_threads(session: AsyncSession, istat_code: str) -> list[CommunityThread]:
    res = await session.execute(
        select(CommunityThread).where(CommunityThread.istat_code == istat_code)
        .order_by(CommunityThread.created_at.desc(), CommunityThread.id.desc())
    )
    return list(res.scalars().all())


async def get_thread(session: AsyncSession, thread_id: int) -> CommunityThread | None:
    return await session.get(CommunityThread, thread_id)


async def create_post(
    session: AsyncSession, *, thread_id: int, body: str, author: str | None = None
) -> CommunityPost:
    row = CommunityPost(thread_id=thread_id, body=body, author=author, status="visible")
    session.add(row)
    await session.flush()
    return row


async def list_posts(
    session: AsyncSession, thread_id: int, *, include_hidden: bool = False
) -> list[CommunityPost]:
    stmt = select(CommunityPost).where(CommunityPost.thread_id == thread_id)
    if not include_hidden:
        stmt = stmt.where(CommunityPost.status == "visible")
    stmt = stmt.order_by(CommunityPost.created_at.asc(), CommunityPost.id.asc())
    return list((await session.execute(stmt)).scalars().all())


async def moderate_post(
    session: AsyncSession, post_id: int, *, status: str
) -> CommunityPost | None:
    post = await session.get(CommunityPost, post_id)
    if post is None:
        return None
    post.status = status
    await session.flush()
    return post
