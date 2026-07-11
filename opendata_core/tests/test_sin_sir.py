"""Test del connettore siti contaminati SIN-SIR (MOSAICO ISPRA, #128 Fase 2a)."""

from __future__ import annotations

import httpx

from opendata_core.sin_sir import ContaminationInfo, SinSirClient


async def test_contamination_at_combina_sin_e_sir(monkeypatch) -> None:
    async def _sin(_lat, _lon):  # noqa: ANN001, ANN202
        return True, "70", ["SSAS"]

    async def _proc(_cod):  # noqa: ANN001, ANN202
        return 25, 9

    async with SinSirClient() as c:
        monkeypatch.setattr(c, "_sin_at", _sin)
        monkeypatch.setattr(c, "_procedimenti_comune", _proc)
        info = await c.contamination_at(40.49, 17.24, "073027")

    assert isinstance(info, ContaminationInfo)
    assert info.contaminato is True and info.sin is True
    assert info.sir_procedimenti == 25 and info.sir_contaminati == 9
    assert info.matrici == ["SSAS"]


async def test_contamination_at_procedimenti_ma_nessuno_contaminato(monkeypatch) -> None:
    async def _sin(_lat, _lon):  # noqa: ANN001, ANN202
        return False, None, []

    async def _proc(_cod):  # noqa: ANN001, ANN202
        return 3, 0  # 3 procedimenti ma nessuno in stato contaminato

    async with SinSirClient() as c:
        monkeypatch.setattr(c, "_sin_at", _sin)
        monkeypatch.setattr(c, "_procedimenti_comune", _proc)
        info = await c.contamination_at(1.0, 2.0, "x")

    assert info is not None and info.contaminato is False
    assert info.sin is False and info.sir_procedimenti == 3 and info.sir_contaminati == 0


async def test_contamination_at_failsafe_entrambe_giu(monkeypatch) -> None:
    async def _boom(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise httpx.ConnectError("down")

    async with SinSirClient() as c:
        monkeypatch.setattr(c, "_sin_at", _boom)
        monkeypatch.setattr(c, "_procedimenti_comune", _boom)
        assert await c.contamination_at(1.0, 2.0, "x") is None


async def test_sin_at_parsing(monkeypatch) -> None:
    async def _query(_layer, _params):  # noqa: ANN001, ANN202
        return {"features": [{"attributes": {"den_sin": "70", "matrice": "SSAS"}}]}

    async with SinSirClient() as c:
        monkeypatch.setattr(c, "_query", _query)
        inside, den, matrici = await c._sin_at(40.49, 17.24)

    assert inside is True and den == "70" and matrici == ["SSAS"]


async def test_sin_at_fuori_da_ogni_sin(monkeypatch) -> None:
    async def _query(_layer, _params):  # noqa: ANN001, ANN202
        return {"features": []}

    async with SinSirClient() as c:
        monkeypatch.setattr(c, "_query", _query)
        inside, den, matrici = await c._sin_at(45.0, 9.0)

    assert inside is False and den is None and matrici == []
