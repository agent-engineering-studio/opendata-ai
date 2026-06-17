"""Router /community — forum civico per comune (thread/post, ruoli, moderazione).

Identità via Clerk. Ruoli: cittadino (default) / moderatore / amministratore, da
tabella community_members o claim Clerk `role`. Dati personali minimi (GDPR): solo
l'id utente Clerk opaco + display name opzionale.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..db.repositories import community as repo
from ..db.session import get_db_session
from ..shared.ratelimit import enforce_rate_limit

router = APIRouter(tags=["community"])


class ThreadIn(BaseModel):
    topic_type: str  # tema | opera | kpi | snapshot
    title: str
    topic_ref: str | None = None


class PostIn(BaseModel):
    body: str


class ModerateIn(BaseModel):
    status: str  # visible | hidden


class RoleIn(BaseModel):
    clerk_user_id: str
    role: str
    display_name: str | None = None


async def _effective_role(session: AsyncSession, user: ClerkUser, istat: str) -> str:
    role = await repo.get_role(session, clerk_user_id=user.subject, istat_code=istat)
    if role == "cittadino":
        claim = (getattr(user, "claims", {}) or {}).get("role")
        if claim in ("moderatore", "amministratore"):
            return claim
    return role


def _thread_dict(t: Any) -> dict[str, Any]:
    return {"id": t.id, "istat_code": t.istat_code, "topic_type": t.topic_type,
            "topic_ref": t.topic_ref, "title": t.title, "created_by": t.created_by,
            "status": t.status, "created_at": t.created_at.isoformat() if t.created_at else None}


def _post_dict(p: Any) -> dict[str, Any]:
    return {"id": p.id, "thread_id": p.thread_id, "author": p.author, "body": p.body,
            "status": p.status, "created_at": p.created_at.isoformat() if p.created_at else None}


@router.get("/community/{istat_code}/threads")
async def threads_list(
    istat_code: str,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    rows = await repo.list_threads(session, istat_code.strip())
    return {"threads": [_thread_dict(t) for t in rows]}


@router.post("/community/{istat_code}/threads", status_code=201)
async def thread_create(
    istat_code: str,
    body: ThreadIn,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="title obbligatorio")
    t = await repo.create_thread(
        session, istat_code=istat_code.strip(), topic_type=body.topic_type,
        title=body.title.strip(), topic_ref=body.topic_ref, created_by=user.subject,
    )
    await session.commit()
    return _thread_dict(t)


@router.get("/community/threads/{thread_id}/posts")
async def posts_list(
    thread_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    rows = await repo.list_posts(session, thread_id)
    return {"posts": [_post_dict(p) for p in rows]}


@router.post("/community/threads/{thread_id}/posts", status_code=201)
async def post_create(
    thread_id: int,
    body: PostIn,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    if not body.body.strip():
        raise HTTPException(status_code=422, detail="body obbligatorio")
    if await repo.get_thread(session, thread_id) is None:
        raise HTTPException(status_code=404, detail="thread non trovato")
    p = await repo.create_post(session, thread_id=thread_id, body=body.body.strip(), author=user.subject)
    await session.commit()
    return _post_dict(p)


@router.post("/community/posts/{post_id}/moderate")
async def post_moderate(
    post_id: int,
    body: ModerateIn,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    # carica post + thread per ricavare l'istat e verificare il ruolo
    from ..db.territory_models import CommunityPost

    post = await session.get(CommunityPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post non trovato")
    thread = await repo.get_thread(session, post.thread_id)
    istat = thread.istat_code if thread else ""
    role = await _effective_role(session, user, istat)
    if not repo.is_moderator(role):
        raise HTTPException(status_code=403, detail="richiede ruolo moderatore/amministratore")
    if body.status not in ("visible", "hidden"):
        raise HTTPException(status_code=422, detail="status deve essere visible|hidden")
    updated = await repo.moderate_post(session, post_id, status=body.status)
    await session.commit()
    return _post_dict(updated)


@router.post("/community/{istat_code}/members/role")
async def member_set_role(
    istat_code: str,
    body: RoleIn,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Assegna un ruolo a un membro (richiede amministratore)."""
    role = await _effective_role(session, user, istat_code.strip())
    if role != "amministratore":
        raise HTTPException(status_code=403, detail="richiede ruolo amministratore")
    m = await repo.set_role(session, clerk_user_id=body.clerk_user_id, istat_code=istat_code.strip(),
                            role=body.role, display_name=body.display_name)
    await session.commit()
    return {"clerk_user_id": m.clerk_user_id, "istat_code": m.istat_code, "role": m.role}
