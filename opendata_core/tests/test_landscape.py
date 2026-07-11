"""Test del connettore vincoli paesaggistici — adattatore Puglia (#128 Fase 2b)."""

from __future__ import annotations

import httpx

from opendata_core.landscape import (
    LandscapeConstraint,
    PugliaPPTRClient,
    constraint_at,
    landscape_adapter,
)
from opendata_core.landscape.puglia import _is_tutela, _parse_identify


def test_is_tutela_distingue_vincoli_da_descrittivi() -> None:
    assert _is_tutela("Territori costieri")
    assert _is_tutela("Boschi")
    assert _is_tutela("Immobili e aree di notevole interesse pubblico")
    # descrittivi/strutturali: NON sono vincoli
    assert not _is_tutela("Figure")
    assert not _is_tutela("Ambiti")
    assert not _is_tutela("Citta consolidata")
    assert not _is_tutela("Siti di rilevanza naturalistica")
    assert not _is_tutela(None)


def test_parse_identify_estrae_solo_tutele() -> None:
    payload = {"results": [
        {"layerName": "Territori costieri"},
        {"layerName": "Citta consolidata"},
        {"layerName": "Grotte"},
        {"layerName": "Figure"},
    ]}
    c = _parse_identify(payload, "http://x")
    assert isinstance(c, LandscapeConstraint)
    assert c.vincolato is True
    assert c.tutele == ["Grotte", "Territori costieri"]
    assert c.regione == "Puglia"


def test_parse_identify_nessuna_tutela_e_esito_valido() -> None:
    c = _parse_identify({"results": [{"layerName": "Citta consolidata"}]}, "u")
    assert c is not None and c.vincolato is False and c.tutele == []


def test_parse_identify_errore_o_forma_inattesa_none() -> None:
    assert _parse_identify({"error": {"code": 400}}, "u") is None
    assert _parse_identify("boh", "u") is None


def test_landscape_adapter_solo_regioni_coperte() -> None:
    assert landscape_adapter("072021") is PugliaPPTRClient  # Gioia del Colle (BA)
    assert landscape_adapter("110001") is PugliaPPTRClient  # provincia BAT
    assert landscape_adapter("058091") is None              # Roma → non coperta
    assert landscape_adapter(None) is None


async def test_constraint_at_regione_non_coperta_none() -> None:
    # comune non pugliese → nessun adattatore → None senza toccare la rete
    assert await constraint_at(lat=41.9, lon=12.5, cod_comune="058091") is None


async def test_pptr_constraint_at_failsafe(monkeypatch) -> None:
    async def _boom(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise httpx.ConnectError("down")

    async with PugliaPPTRClient() as c:
        monkeypatch.setattr(c._client, "get", _boom)
        assert await c.constraint_at(40.99, 17.22) is None
