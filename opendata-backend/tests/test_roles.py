"""RBAC — role resolution + `require_role` gating + bootstrap admin (#235)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import MetaData, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from opendata_backend.auth import ClerkUser, require_admin, require_role
from opendata_backend.auth import dependencies as auth_dep
from opendata_backend.config import Settings, get_settings
from opendata_backend.db.models import Base, User
from opendata_backend.db.repositories import users as users_repo
from opendata_backend.db.session import get_db_session


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


@pytest.fixture
async def sm() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _client(sm, *, subject: str, email: str | None, auth_enabled: bool = True,
            bootstrap: str | None = None) -> TestClient:
    async def _user() -> ClerkUser:
        return ClerkUser(subject=subject, email=email, claims={})

    async def _db() -> AsyncIterator[AsyncSession]:
        async with sm() as session:
            yield session

    app = FastAPI()

    @app.get("/admin-only")
    async def admin_only(user: ClerkUser = Depends(require_admin)) -> dict:
        return {"role": user.role}

    @app.get("/staff")
    async def staff(user: ClerkUser = Depends(require_role("admin", "regione", "comune"))) -> dict:
        return {"role": user.role}

    app.dependency_overrides[get_settings] = lambda: Settings(  # type: ignore[call-arg]
        auth_enabled=auth_enabled, bootstrap_admin_email=bootstrap,
    )
    app.dependency_overrides[auth_dep.require_user] = _user
    app.dependency_overrides[get_db_session] = _db
    return TestClient(app)


def test_dev_bypass_is_admin(sm) -> None:
    c = _client(sm, subject="dev", email=None, auth_enabled=False)
    assert c.get("/admin-only").json() == {"role": "admin"}


def test_new_user_defaults_to_cittadino_and_is_denied_admin(sm) -> None:
    c = _client(sm, subject="kc_1", email="tizio@comune.it")
    # cittadino cannot reach the admin route …
    assert c.get("/admin-only").status_code == 403
    # … but is a real synced row with the default role.
    assert c.get("/staff").status_code == 403  # cittadino is not staff either


def test_bootstrap_email_is_promoted_to_admin(sm) -> None:
    c = _client(sm, subject="kc_boss", email="Boss@Regione.IT", bootstrap="boss@regione.it")
    r = c.get("/admin-only")
    assert r.status_code == 200
    assert r.json() == {"role": "admin"}


async def test_set_role_promotes_and_staff_gate(sm) -> None:
    # Sync the user (cittadino), then an admin promotes them to "comune".
    async with sm() as s:
        await users_repo.get_or_create(s, clerk_user_id="kc_2", email="a@b.it")
        await s.commit()
    async with sm() as s:
        updated = await users_repo.set_role(s, clerk_user_id="kc_2", role="comune")
        await s.commit()
        assert updated is not None and updated.role == "comune"

    c = _client(sm, subject="kc_2", email="a@b.it")
    assert c.get("/staff").status_code == 200      # comune is staff
    assert c.get("/admin-only").status_code == 403  # but not admin

    # set_role on an unknown user → None (caller 404s)
    async with sm() as s:
        assert await users_repo.set_role(s, clerk_user_id="nope", role="admin") is None


async def test_role_persisted_on_first_login(sm) -> None:
    _client(sm, subject="kc_3", email="c@d.it").get("/staff")
    async with sm() as s:
        row = (await s.execute(select(User).where(User.clerk_user_id == "kc_3"))).scalar_one()
        assert row.role == "cittadino"
