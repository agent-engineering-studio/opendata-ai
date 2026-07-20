"""Test del servizio /maturity con CKAN mockato (pytest-httpx) su SQLite.

Niente Redis (cache fail-open → no-op) né ANTHROPIC_API_KEY (semantico saltato):
assessment deterministico. Copre harvest→assess→persisti→scorecard→ranking, ossia
la logica dietro il router.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pytest_httpx import HTTPXMock
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base
from opendata_backend.db.territory_models import DatasetQuality, MaturityAssessment
from opendata_backend.maturity.service import (
    _regional_ckan,
    build_ranking,
    build_scorecard,
    run_assessment,
)

_ORG = {"id": "org-gdc", "name": "comune-di-gioia-del-colle", "title": "Comune di Gioia del Colle"}


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        anthropic_api_key=None,
        llm_provider="claude",  # provider=claude + no key → semantico saltato (offline)
        claude_classify_model="claude-haiku-4-5-20251001",
        maturity_max_datasets=50,
        maturity_cache_ttl_seconds=3600,
    )


def _pkg(i: int, *, good: bool) -> dict:
    if good:
        return {
            "id": f"good-{i}", "title": f"Statistiche {i}", "notes": "Descrizione chiara.",
            "tags": [{"name": "statistica"}], "theme": "POP", "license_id": "cc-by-4.0",
            "isopen": True, "metadata_modified": "2026-04-01T00:00:00", "frequency": "annual",
            "resources": [{"format": "CSV", "url": f"https://ex.it/{i}.csv"}],
        }
    return {
        "id": f"bad-{i}", "title": f"Doc {i}", "notes": "", "tags": [], "isopen": False,
        "metadata_modified": "2021-01-01T00:00:00",
        "resources": [{"format": "PDF", "url": f"https://ex.it/{i}.pdf"}],
    }


def _strip_schema(metadata: MetaData) -> None:
    for table in metadata.tables.values():
        table.schema = None


@pytest.fixture(autouse=True)
def _no_anthropic(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


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


def _add_harvest_responses(httpx_mock: HTTPXMock, packages: list[dict]) -> None:
    httpx_mock.add_response(json={"success": True, "result": _ORG})
    httpx_mock.add_response(
        json={"success": True, "result": {"count": len(packages), "results": packages}}
    )


async def test_run_assessment_persists_and_builds_scorecard(
    session: AsyncSession, httpx_mock: HTTPXMock
) -> None:
    packages = [_pkg(i, good=True) for i in range(3)] + [_pkg(i, good=False) for i in range(2)]
    _add_harvest_responses(httpx_mock, packages)

    sc = await run_assessment(
        session, entity="comune-di-gioia-del-colle", base_url=None,
        settings=_settings(), force=True,
    )

    assert sc["entity"]["name"] == "Comune di Gioia del Colle"
    assert sc["entity"]["ckan_org_id"] == "org-gdc"
    assert sc["n_datasets"] == 5
    assert 0.0 <= sc["overall"] <= 100.0
    assert sc["level"] in {"Beginner", "Follower", "Fast-tracker", "Trend-setter"}
    assert set(sc["dimensions"]) == {"policy", "portal", "quality", "impact"}
    assert any(r["code"] == "open_license" for r in sc["recommendations"])

    # breakdown per dimensione (Fase B): una voce per dimensione, con drivers
    bd = {b["dimension"]: b for b in sc["dimension_breakdown"]}
    assert set(bd) == {"policy", "portal", "quality", "impact"}
    assert bd["quality"]["drivers"] and "description" in bd["quality"]

    # copertura tematica (Fase A): tipo ente dedotto = comune, con settori core
    cov = sc["coverage"]
    assert cov is not None and cov["entity_type"] == "comune"
    assert 0.0 <= cov["coverage_score"] <= 100.0
    assert len(cov["hvd_present"]) + len(cov["hvd_missing"]) == 6
    # un comune con solo dataset statistici → settori core mancanti segnalati
    assert cov["missing_core"]
    assert any(r["code"] == "sector_gap" for r in sc["recommendations"])

    # persistenza snapshot
    dq = (await session.execute(select(func.count()).select_from(DatasetQuality))).scalar_one()
    ma = (await session.execute(select(func.count()).select_from(MaturityAssessment))).scalar_one()
    assert dq == 5
    assert ma == 1


async def test_trend_grows_and_ranking(session: AsyncSession, httpx_mock: HTTPXMock) -> None:
    packages = [_pkg(i, good=True) for i in range(4)]
    _add_harvest_responses(httpx_mock, packages)
    _add_harvest_responses(httpx_mock, packages)

    sc1 = await run_assessment(
        session, entity="comune-di-gioia-del-colle", base_url=None, settings=_settings(), force=True
    )
    eid = sc1["entity"]["id"]
    sc2 = await run_assessment(
        session, entity="comune-di-gioia-del-colle", base_url=None, settings=_settings(), force=True
    )
    assert sc2["entity"]["id"] == eid  # stesso ente (upsert per ckan_org_id)

    scorecard = await build_scorecard(session, eid)
    assert len(scorecard["trend"]) == 2

    ranking = await build_ranking(session, entity_type="ente", region=None)
    assert ranking["count"] == 1
    assert ranking["median_overall"] is not None
    assert ranking["ranking"][0]["entity"]["id"] == eid


async def test_peer_comparison(session: AsyncSession) -> None:
    """Due comuni valutati → lo scorecard espone il confronto con enti simili."""
    from datetime import datetime, timezone

    from opendata_backend.db.repositories import maturity as repo

    def _scores(overall, policy, portal, quality, impact, level):
        return SimpleNamespace(
            overall=overall, policy=policy, portal=portal,
            quality=quality, impact=impact, level=level,
        )

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # Ente A: forte. Ente B: più debole. Stesso tipo "comune".
    a = await repo.upsert_entity(session, name="Comune A", ckan_org_id="org-a", entity_type="comune")
    b = await repo.upsert_entity(session, name="Comune B", ckan_org_id="org-b", entity_type="comune")
    await repo.save_assessment(
        session, entity_id=a.id, scores=_scores(70, 80, 70, 65, 60, "Fast-tracker"),
        details={"n_datasets": 10}, assessed_at=now,
    )
    await repo.save_assessment(
        session, entity_id=b.id, scores=_scores(40, 50, 40, 35, 30, "Follower"),
        details={"n_datasets": 5}, assessed_at=now,
    )
    await session.commit()

    sc_a = await build_scorecard(session, a.id)
    pc = sc_a["peer_comparison"]
    assert pc is not None
    assert pc["cluster_label"] == "comuni"
    assert pc["count"] == 2
    assert pc["rank"] == 1  # A è il migliore
    assert pc["better_than_pct"] == 50  # davanti a metà del cluster
    assert pc["median_overall"] == 55.0  # mediana di 70 e 40
    assert set(pc["median_dimensions"]) == {"policy", "portal", "quality", "impact"}

    # L'ente più debole è ultimo, non supera nessuno.
    sc_b = await build_scorecard(session, b.id)
    assert sc_b["peer_comparison"]["rank"] == 2
    assert sc_b["peer_comparison"]["better_than_pct"] == 0


async def test_regione_pptr_indicator(session: AsyncSession) -> None:
    """Indicatore PPTR (#168): presente e onesto per le Regioni; None per i comuni."""
    from datetime import datetime, timezone

    from opendata_backend.db.repositories import maturity as repo

    def _sc(o, p, po, q, i, lvl):
        return SimpleNamespace(overall=o, policy=p, portal=po, quality=q, impact=i, level=lvl)

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    pug = await repo.upsert_entity(session, name="Regione Puglia", ckan_org_id="rp",
                                   entity_type="regione", region="Puglia")
    laz = await repo.upsert_entity(session, name="Regione Lazio", ckan_org_id="rl",
                                   entity_type="regione", region="Lazio")
    com = await repo.upsert_entity(session, name="Comune X", ckan_org_id="cx",
                                   entity_type="comune")
    for e in (pug, laz, com):
        await repo.save_assessment(session, entity_id=e.id,
                                   scores=_sc(50, 50, 50, 50, 50, "Follower"),
                                   details={"n_datasets": 8}, assessed_at=now)
    await session.commit()

    # Puglia: coperta → interrogabile, con formato/licenza.
    ind = (await build_scorecard(session, pug.id))["regione_pptr"]
    assert ind is not None and ind["queryable"] is True and ind["stato"] == "interrogabile"
    assert ind["formato"] and ind["licenza"]
    # Lazio: regione ma senza adattatore → onesto "non rilevato" (mai falso "assente").
    ind_l = (await build_scorecard(session, laz.id))["regione_pptr"]
    assert ind_l["queryable"] is False and ind_l["stato"] == "non rilevato"
    # Comune: l'indicatore non si applica → None (la UI lo nasconde).
    assert (await build_scorecard(session, com.id))["regione_pptr"] is None


async def test_peer_comparison_none_when_alone(session: AsyncSession) -> None:
    """Un solo ente del tipo → nessun confronto possibile (None)."""
    from datetime import datetime, timezone

    from opendata_backend.db.repositories import maturity as repo

    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    e = await repo.upsert_entity(session, name="Solo", ckan_org_id="org-s", entity_type="comune")
    await repo.save_assessment(
        session, entity_id=e.id,
        scores=SimpleNamespace(overall=50, policy=50, portal=50, quality=50, impact=50, level="Follower"),
        details={"n_datasets": 3}, assessed_at=now,
    )
    await session.commit()
    sc = await build_scorecard(session, e.id)
    assert sc["peer_comparison"] is None


async def test_scorecard_404_when_missing(session: AsyncSession) -> None:
    assert await build_scorecard(session, 999) is None


async def test_insufficient_data_yields_guida(
    session: AsyncSession, httpx_mock: HTTPXMock
) -> None:
    """Comune con pochi dataset (< soglia) → insufficient_data + guida operativa."""
    _add_harvest_responses(httpx_mock, [_pkg(0, good=True)])  # 1 solo dataset < 3
    sc = await run_assessment(
        session, entity="comune-di-gioia-del-colle", base_url=None,
        settings=_settings(), force=True, comune_nome="Gioia del Colle",
    )
    assert sc["insufficient_data"] is True
    assert sc["guida"] is not None
    assert sc["guida"]["passi"] and "titolo" in sc["guida"]
    assert "nota" in sc["guida"]


def test_regional_ckan_mapping() -> None:
    assert "puglia" in (_regional_ckan("072021") or "").lower()  # Bari → Puglia
    assert _regional_ckan("001059") is None  # Torino → non mappato
    assert _regional_ckan(None) is None
