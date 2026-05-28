"""Per-user state — favorites + history backed by Postgres."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser, require_user
from ..db.repositories import favorites as favorites_repo
from ..db.repositories import history as history_repo
from ..db.repositories import users as users_repo
from ..db.session import get_db_session

router = APIRouter(tags=["me"])


class FavoriteIn(BaseModel):
    source: str
    dataset_id: str
    dataset_name: str | None = None
    metadata: dict | None = None


class FavoriteOut(BaseModel):
    id: int
    source: str
    dataset_id: str
    dataset_name: str | None
    metadata: dict | None
    created_at: str


class HistoryOut(BaseModel):
    id: int
    query: str
    response_summary: str | None
    created_at: str


async def _local_user_id(session: AsyncSession, user: ClerkUser) -> int:
    row = await users_repo.get_or_create(
        session, clerk_user_id=user.subject, email=user.email
    )
    return row.id


@router.get("/me/favorites", response_model=list[FavoriteOut])
async def list_favorites(
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(require_user),
) -> list[FavoriteOut]:
    uid = await _local_user_id(session, user)
    rows = await favorites_repo.list_for_user(session, user_id=uid)
    return [
        FavoriteOut(
            id=r.id,
            source=r.source,
            dataset_id=r.dataset_id,
            dataset_name=r.dataset_name,
            metadata=r.metadata_,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/me/favorites", response_model=FavoriteOut, status_code=201)
async def add_favorite(
    body: FavoriteIn,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(require_user),
) -> FavoriteOut:
    uid = await _local_user_id(session, user)
    row = await favorites_repo.add(
        session,
        user_id=uid,
        source=body.source,
        dataset_id=body.dataset_id,
        dataset_name=body.dataset_name,
        metadata=body.metadata,
    )
    await session.commit()
    return FavoriteOut(
        id=row.id,
        source=row.source,
        dataset_id=row.dataset_id,
        dataset_name=row.dataset_name,
        metadata=row.metadata_,
        created_at=row.created_at.isoformat(),
    )


@router.delete("/me/favorites/{source}/{dataset_id}", status_code=204)
async def remove_favorite(
    source: str,
    dataset_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(require_user),
) -> None:
    uid = await _local_user_id(session, user)
    n = await favorites_repo.remove(
        session, user_id=uid, source=source, dataset_id=dataset_id
    )
    if n == 0:
        raise HTTPException(status_code=404, detail="favorite not found")
    await session.commit()


@router.get("/me/history", response_model=list[HistoryOut])
async def list_history(
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(require_user),
) -> list[HistoryOut]:
    uid = await _local_user_id(session, user)
    rows = await history_repo.list_for_user(session, user_id=uid)
    return [
        HistoryOut(
            id=r.id,
            query=r.query,
            response_summary=r.response_summary,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
