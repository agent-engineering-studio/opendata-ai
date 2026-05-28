"""Tests for the cache-aware classify service.

Uses the existing SQLite + fakeredis machinery so we don't touch the network.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.cache.state import set_redis
from opendata_backend.classify.service import classify_dataset
from opendata_backend.db.models import Base


def _strip_schema(metadata: MetaData) -> None:
    for table in metadata.tables.values():
        table.schema = None


@dataclass
class _StubResp:
    scores: dict[str, float]
    model: str = "claude-haiku-4-5-stub"
    raw: str = ""
    usage: dict[str, int] = None  # type: ignore[assignment]


class _StubClassifier:
    def __init__(self, scores: dict[str, float]) -> None:
        self.calls = 0
        self._scores = scores

    async def classify(self, *, dataset_name, dataset_description, taxonomy):
        self.calls += 1
        return _StubResp(scores={c: self._scores.get(c, 0.0) for c in taxonomy})


@pytest.fixture
async def db_session() -> AsyncSession:
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def redis_off():
    set_redis(None)
    yield
    set_redis(None)


@pytest.fixture
def redis_on():
    import fakeredis.aioredis

    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    set_redis(client)
    yield client
    set_redis(None)


async def test_first_call_hits_classifier_and_persists(db_session, redis_off) -> None:
    clf = _StubClassifier({"energy": 0.91, "transport": 0.04})
    res = await classify_dataset(
        db_session,
        clf,
        source="ckan",
        dataset_id="solar-stations",
        dataset_name="Solar stations 2026",
        dataset_description="Map of solar charging stations.",
        taxonomy=["energy", "transport"],
    )
    assert clf.calls == 1
    assert res.cached is False
    assert res.scores == {"energy": 0.91, "transport": 0.04}


async def test_second_call_uses_postgres_cache(db_session, redis_off) -> None:
    clf = _StubClassifier({"energy": 0.91, "transport": 0.04})
    await classify_dataset(
        db_session,
        clf,
        source="ckan",
        dataset_id="solar-stations",
        dataset_name="Solar stations 2026",
        dataset_description="…",
        taxonomy=["energy", "transport"],
    )
    res = await classify_dataset(
        db_session,
        clf,
        source="ckan",
        dataset_id="solar-stations",
        dataset_name="Solar stations 2026",
        dataset_description="…",
        taxonomy=["energy", "transport"],
    )
    assert clf.calls == 1  # second call did not invoke the classifier
    assert res.cached is True
    assert res.scores == {"energy": 0.91, "transport": 0.04}


async def test_taxonomy_order_does_not_change_cache_key(db_session, redis_off) -> None:
    clf = _StubClassifier({"energy": 0.5, "transport": 0.5})
    await classify_dataset(
        db_session, clf,
        source="ckan", dataset_id="d1", dataset_name="n", dataset_description=None,
        taxonomy=["energy", "transport"],
    )
    # Reorder the taxonomy — should still hit the persisted row.
    res = await classify_dataset(
        db_session, clf,
        source="ckan", dataset_id="d1", dataset_name="n", dataset_description=None,
        taxonomy=["transport", "energy"],
    )
    assert clf.calls == 1
    assert res.cached is True


async def test_redis_short_circuits_postgres(db_session, redis_on) -> None:
    clf_a = _StubClassifier({"energy": 0.8})
    res1 = await classify_dataset(
        db_session, clf_a,
        source="ckan", dataset_id="d2", dataset_name="n", dataset_description=None,
        taxonomy=["energy"],
    )
    assert res1.cached is False

    # Now: even if we hand it a different classifier, the redis cache returns
    # the first value WITHOUT going to Postgres or the LLM.
    clf_b = _StubClassifier({"energy": 0.1})
    res2 = await classify_dataset(
        db_session, clf_b,
        source="ckan", dataset_id="d2", dataset_name="n", dataset_description=None,
        taxonomy=["energy"],
    )
    assert clf_b.calls == 0
    assert res2.cached is True
    assert res2.scores == {"energy": 0.8}


async def test_empty_taxonomy_rejected(db_session, redis_off) -> None:
    clf = _StubClassifier({})
    with pytest.raises(ValueError, match="taxonomy"):
        await classify_dataset(
            db_session, clf,
            source="ckan", dataset_id="d3", dataset_name="n", dataset_description=None,
            taxonomy=[],
        )
