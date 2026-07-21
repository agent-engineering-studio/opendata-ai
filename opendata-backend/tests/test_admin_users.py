"""Admin API — /admin/users list + role PATCH, gated by require_admin (#235 F2)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from opendata_backend.auth import ClerkUser
from opendata_backend.auth import dependencies as auth_dep
from opendata_backend.config import Settings, get_settings
from opendata_backend.db.models import Base, User
from opendata_backend.db.session import get_db_session
from opendata_backend.routers import admin


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


@pytest.fixture
async def sm() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add_all([
            User(clerk_user_id="admin_1", email="admin@r.it", role="admin"),
            User(clerk_user_id="cit_1", email="c1@r.it", role="cittadino"),
            User(clerk_user_id="com_1", email="c2@r.it", role="comune"),
        ])
        await s.commit()
    yield maker
    await engine.dispose()


def _client(sm, *, subject: str) -> TestClient:
    async def _user() -> ClerkUser:
        return ClerkUser(subject=subject, email=None, claims={})

    async def _db() -> AsyncIterator[AsyncSession]:
        async with sm() as session:
            yield session

    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[get_settings] = lambda: Settings(auth_enabled=True)  # type: ignore[call-arg]
    app.dependency_overrides[auth_dep.require_user] = _user
    app.dependency_overrides[get_db_session] = _db
    return TestClient(app)


def test_non_admin_is_forbidden(sm) -> None:
    c = _client(sm, subject="cit_1")
    assert c.get("/admin/users").status_code == 403
    assert c.patch("/admin/users/2/role", json={"role": "comune"}).status_code == 403


def test_admin_lists_and_filters(sm) -> None:
    c = _client(sm, subject="admin_1")
    rows = c.get("/admin/users").json()
    assert {r["role"] for r in rows} == {"admin", "cittadino", "comune"}
    only_com = c.get("/admin/users", params={"role": "comune"}).json()
    assert [r["clerk_user_id"] for r in only_com] == ["com_1"]
    assert c.get("/admin/users", params={"role": "boh"}).status_code == 422


def test_admin_changes_role(sm) -> None:
    c = _client(sm, subject="admin_1")
    cit = next(r for r in c.get("/admin/users").json() if r["clerk_user_id"] == "cit_1")
    res = c.patch(f"/admin/users/{cit['id']}/role", json={"role": "regione"})
    assert res.status_code == 200
    assert res.json()["role"] == "regione"
    # persisted
    again = next(r for r in c.get("/admin/users").json() if r["clerk_user_id"] == "cit_1")
    assert again["role"] == "regione"


def test_patch_validation_and_404(sm) -> None:
    c = _client(sm, subject="admin_1")
    cit = next(r for r in c.get("/admin/users").json() if r["clerk_user_id"] == "cit_1")
    assert c.patch(f"/admin/users/{cit['id']}/role", json={"role": "boh"}).status_code == 422
    assert c.patch("/admin/users/99999/role", json={"role": "comune"}).status_code == 404


def test_admin_cannot_self_demote(sm) -> None:
    c = _client(sm, subject="admin_1")
    me = next(r for r in c.get("/admin/users").json() if r["clerk_user_id"] == "admin_1")
    res = c.patch(f"/admin/users/{me['id']}/role", json={"role": "comune"})
    assert res.status_code == 400
    # can still re-affirm own admin role (no-op)
    assert c.patch(f"/admin/users/{me['id']}/role", json={"role": "admin"}).status_code == 200
