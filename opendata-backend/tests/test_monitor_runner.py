"""Test del runner di monitoraggio: check_target/run_monitor, notifica solo sui nuovi (#88)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.config import Settings
from opendata_backend.db.models import Base
from opendata_backend.db.repositories import monitor as repo
from opendata_backend.monitor import runner


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


@pytest.fixture
async def session() -> AsyncSession:
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


def _settings() -> Settings:
    return Settings(auth_enabled=False)  # type: ignore[call-arg]


async def _fake_fetch_ok(*a, **k):
    return {"status_code": 200, "errore": None, "last_modified": None, "testo": "a,b\n1,2\n"}


async def _fake_fetch_404(*a, **k):
    return {"status_code": 404, "errore": None, "last_modified": None, "testo": None}


async def test_check_target_link_ok_no_notification(session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_fetch", _fake_fetch_ok)
    t = await repo.create_target(session, url="https://x.it/a.csv")
    await session.commit()

    esito = await runner.check_target(session, t, settings=_settings(), ora=datetime.now(timezone.utc))
    assert esito["esito"] == "ok"
    assert esito["notificato"] is False

    run = await repo.latest_run(session, t.id)
    assert run is not None and run.esito == "ok"


async def test_check_target_broken_link_notifies_on_first_finding(session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_fetch", _fake_fetch_404)
    sent: list[tuple] = []

    async def _fake_webhook(url: str, payload: dict) -> bool:
        sent.append((url, payload))
        return True

    monkeypatch.setattr(runner, "send_webhook", _fake_webhook)
    t = await repo.create_target(session, url="https://x.it/a.csv", webhook_url="https://hooks.example.com/x")
    await session.commit()

    esito = await runner.check_target(session, t, settings=_settings(), ora=datetime.now(timezone.utc))
    assert esito["esito"] == "critico"
    assert esito["notificato"] is True
    assert len(sent) == 1
    assert sent[0][1]["esito"] == "critico"


async def test_check_target_does_not_renotify_same_issue(session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_fetch", _fake_fetch_404)
    calls = []

    async def _fake_webhook(url: str, payload: dict) -> bool:
        calls.append(1)
        return True

    monkeypatch.setattr(runner, "send_webhook", _fake_webhook)
    t = await repo.create_target(session, url="https://x.it/a.csv", webhook_url="https://hooks.example.com/x")
    await session.commit()

    r1 = await runner.check_target(session, t, settings=_settings(), ora=datetime.now(timezone.utc))
    await session.commit()
    r2 = await runner.check_target(session, t, settings=_settings(), ora=datetime.now(timezone.utc))

    assert r1["notificato"] is True
    assert r2["notificato"] is False  # stesso problema, già notificato ieri: niente spam
    assert len(calls) == 1
    assert r2["esito"] == "critico"  # il problema persiste, ma non ri-notifica


async def test_run_monitor_one_target_failure_does_not_block_others(session: AsyncSession, monkeypatch) -> None:
    good = await repo.create_target(session, url="https://x.it/good.csv")
    bad = await repo.create_target(session, url="https://x.it/bad.csv")
    await session.commit()

    async def _selective_fetch(url: str, *a, **k):
        if "bad" in url:
            raise RuntimeError("boom")
        return await _fake_fetch_ok()

    monkeypatch.setattr(runner, "_fetch", _selective_fetch)
    summary = await runner.run_monitor(session, settings=_settings())

    assert summary["n_target"] == 2
    esiti = {r["target_id"]: r["esito"] for r in summary["risultati"]}
    assert esiti[good.id] == "ok"
    assert esiti[bad.id] == "errore"


async def test_check_target_link_ok_email_not_configured_is_skipped(session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(runner, "_fetch", _fake_fetch_404)
    t = await repo.create_target(session, url="https://x.it/a.csv", notify_email="ente@example.it")
    await session.commit()
    # send_email non monkeypatchato: usa il vero adapter, che salta senza SMTP configurato.
    esito = await runner.check_target(session, t, settings=_settings(), ora=datetime.now(timezone.utc))
    assert esito["notificato"] is False
