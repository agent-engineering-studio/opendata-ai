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

    # 7 × 0.05s in serie ≈ 0.35s; in parallelo ≈ 0.05s. Soglia generosa.
    assert elapsed < 0.2, f"lenti non parallele: {elapsed:.3f}s"
    assert set(out) == {
        "zona", "zone_comm", "commercio", "turismo", "lavoro", "trasporti", "welfare"
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
    )
    out = await s._resolve_all_lenses(_REQ)

    assert out["commercio"] is None         # eccezione isolata → None
    assert out["turismo"] == {"ok": True}   # le altre sopravvivono
