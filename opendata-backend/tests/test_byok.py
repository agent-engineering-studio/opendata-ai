"""BYOK — key encryption/validation, repo persistence, and the LLM-access gate
(402 unless the user has a BYOK key or a paid subscription tier)."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from opendata_backend import byok
from opendata_backend.config import Settings
from opendata_backend.db.models import Base
from opendata_backend.db.repositories import users as users_repo
from opendata_backend.llm_access import _is_paid, _resolve_byok


def _strip_schema(metadata: MetaData) -> None:
    for table in metadata.tables.values():
        table.schema = None


@pytest.fixture
async def sqlite_factory():
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


# ── crypto + validation (pure) ───────────────────────────────────────────


def test_encrypt_roundtrip() -> None:
    k = byok.generate_encryption_key()
    enc = byok.encrypt_key("sk-ant-abc123", encryption_key=k)
    assert enc != "sk-ant-abc123"  # not stored in the clear
    assert byok.decrypt_key(enc, encryption_key=k) == "sk-ant-abc123"


def test_decrypt_with_wrong_key_raises() -> None:
    enc = byok.encrypt_key("sk-ant-abc123", encryption_key=byok.generate_encryption_key())
    with pytest.raises(byok.BYOKError):
        byok.decrypt_key(enc, encryption_key=byok.generate_encryption_key())


@pytest.mark.parametrize(
    "provider,key,expected",
    [
        ("claude", "sk-ant-xyz", "claude"),
        ("ollama_cloud", "abcd1234efgh", "ollama_cloud"),
        ("ollama_local", "http://localhost:11434", "ollama_local"),
    ],
)
def test_validate_ok(provider, key, expected) -> None:
    assert byok.validate_key(provider, key) == expected


@pytest.mark.parametrize(
    "provider,key",
    [
        ("claude", "not-a-key"),  # wrong prefix
        ("claude", ""),  # empty
        ("ollama_local", "localhost:11434"),  # missing scheme
        ("ollama_cloud", "short"),  # too short
        ("bogus", "whatever"),  # unknown provider
    ],
)
def test_validate_rejects(provider, key) -> None:
    with pytest.raises(byok.BYOKError):
        byok.validate_key(provider, key)


# ── tier gate helper ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tier,paid",
    [("free", False), ("", False), (None, False), ("pro", True), ("sostenitore", True)],
)
def test_is_paid(tier, paid) -> None:
    assert _is_paid(tier) is paid


# ── repo persistence + decryption ────────────────────────────────────────


async def test_set_and_resolve_byok(sqlite_factory) -> None:
    enc_key = byok.generate_encryption_key()
    settings = Settings(byok_encryption_key=enc_key)  # type: ignore[call-arg]

    async with sqlite_factory() as s:
        enc = byok.encrypt_key("sk-ant-secret", encryption_key=enc_key)
        await users_repo.set_byok(
            s, clerk_user_id="u1", provider="claude", key_encrypted=enc
        )
        await s.commit()

    async with sqlite_factory() as s:
        row = await users_repo.get_by_clerk_id(s, clerk_user_id="u1")
        assert row is not None and row.byok_provider == "claude"
        creds = await _resolve_byok(row, settings)
        assert creds is not None
        assert creds.provider == "claude"
        assert creds.secret == "sk-ant-secret"


async def test_clear_byok(sqlite_factory) -> None:
    enc_key = byok.generate_encryption_key()
    settings = Settings(byok_encryption_key=enc_key)  # type: ignore[call-arg]
    async with sqlite_factory() as s:
        enc = byok.encrypt_key("token12345", encryption_key=enc_key)
        await users_repo.set_byok(
            s, clerk_user_id="u2", provider="ollama_cloud", key_encrypted=enc, model="gpt-oss:120b"
        )
        await s.commit()
    async with sqlite_factory() as s:
        await users_repo.clear_byok(s, clerk_user_id="u2")
        await s.commit()
    async with sqlite_factory() as s:
        row = await users_repo.get_by_clerk_id(s, clerk_user_id="u2")
        assert row is not None and row.byok_provider is None
        assert await _resolve_byok(row, settings) is None


async def test_resolve_byok_none_when_unset(sqlite_factory) -> None:
    settings = Settings(byok_encryption_key=byok.generate_encryption_key())  # type: ignore[call-arg]
    async with sqlite_factory() as s:
        row = await users_repo.get_or_create(s, clerk_user_id="u3")
        await s.commit()
        assert await _resolve_byok(row, settings) is None
