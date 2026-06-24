"""Test della risoluzione PARALLELA delle lenti (P1, perf).

`_resolve_all_lenses` deve girare in parallelo (non in serie) e isolare le
eccezioni di una singola lente senza affondare le altre.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from opendata_backend.factory import OrchestratorSession
from opendata_backend.orchestrator.programma import ProgrammaRequest

_REQ = ProgrammaRequest(cod_comune="072021")
_LENSES = (
    "_resolve_zona", "_resolve_zone_commerciali", "_resolve_commercio",
    "_resolve_turismo", "_resolve_lavoro", "_resolve_trasporti", "_resolve_welfare",
    "_resolve_istruzione", "_resolve_ambiente", "_resolve_sanita", "_resolve_comparabili",
)


def _session_with(**resolvers) -> OrchestratorSession:
    s = OrchestratorSession.__new__(OrchestratorSession)  # niente __init__: serve solo self._resolve_*
    for name, fn in resolvers.items():
        setattr(s, name, fn)
    return s


@pytest.mark.asyncio
async def test_resolve_all_lenses_runs_in_parallel() -> None:
    async def slow(tag: str) -> dict:
        await asyncio.sleep(0.05)
        return {"tag": tag}

    s = _session_with(**{name: (lambda req, t=name: slow(t)) for name in _LENSES})
    t0 = time.perf_counter()
    out = await s._resolve_all_lenses(_REQ)
    elapsed = time.perf_counter() - t0

    # 10 × 0.05s in serie ≈ 0.50s; in parallelo ≈ 0.05s. Soglia generosa.
    assert elapsed < 0.2, f"lenti non parallele: {elapsed:.3f}s"
    assert set(out) == {
        "zona", "zone_comm", "commercio", "turismo", "lavoro", "trasporti",
        "welfare", "istruzione", "ambiente", "sanita", "comparabili",
    }
    assert out["commercio"] == {"tag": "_resolve_commercio"}


@pytest.mark.asyncio
async def test_resolve_all_lenses_isolates_exceptions() -> None:
    async def ok() -> dict:
        return {"ok": True}

    async def boom() -> dict:
        raise RuntimeError("connector down")

    s = _session_with(
        _resolve_zona=lambda req: ok(),
        _resolve_zone_commerciali=lambda req: ok(),
        _resolve_commercio=lambda req: boom(),   # esplode
        _resolve_turismo=lambda req: ok(),
        _resolve_lavoro=lambda req: ok(),
        _resolve_trasporti=lambda req: ok(),
        _resolve_welfare=lambda req: ok(),
        _resolve_istruzione=lambda req: ok(),
        _resolve_ambiente=lambda req: ok(),
        _resolve_sanita=lambda req: ok(),
    )
    out = await s._resolve_all_lenses(_REQ)

    assert out["commercio"] is None         # eccezione isolata → None
    assert out["turismo"] == {"ok": True}   # le altre sopravvivono
    assert out["istruzione"] == {"ok": True}
    assert out["ambiente"] == {"ok": True}
    assert out["sanita"] == {"ok": True}


@pytest.mark.asyncio
async def test_resolve_comparabili_excludes_self_by_slug(monkeypatch) -> None:
    """Fase B: i comparabili peer escludono i progetti del comune stesso — i
    `territori` OpenCoesione sono slug ('gioia-del-colle-comune'), quindi il match
    self usa il nome slugificato. Sopravvivono solo i peer, con URL /progetti/."""
    import opendata_core.opencoesione as ocmod

    class _FakeOC:
        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

        async def search_projects(self, **_):  # noqa: ANN003, ANN201
            return {"results": [
                {"clp": "SELF1", "titolo": "Progetto locale", "tema": "x",
                 "finanziamento_totale": 9_000_000.0, "territori": ["gioia-del-colle-comune"]},
                {"clp": "PEER1", "titolo": "Hub Altamura", "tema": "trasporti",
                 "finanziamento_totale": 2_100_000.0, "territori": ["altamura-comune"]},
            ]}

    monkeypatch.setattr(ocmod, "OpenCoesioneClient", _FakeOC)
    req = ProgrammaRequest(cod_comune="072021", comune_nome="Gioia del Colle", modalita="idee")
    out = await OrchestratorSession._resolve_comparabili_uncached(req)
    assert out is not None
    clps = {p["clp"] for p in out["progetti"]}
    assert clps == {"PEER1"}  # SELF1 escluso via slug
    assert out["progetti"][0]["url"].endswith("/progetti/peer1/")
