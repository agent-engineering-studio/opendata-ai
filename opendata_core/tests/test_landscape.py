"""Test del connettore vincoli paesaggistici — adattatore Puglia (#128 Fase 2b)."""

from __future__ import annotations

import httpx

from opendata_core.landscape import (
    LandscapeConstraint,
    PugliaPPTRClient,
    constraint_at,
    landscape_adapter,
    landscape_adapter_for,
    landscape_service_status,
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


def test_landscape_adapter_for_slug_iniettato() -> None:
    # Selezione per slug provider iniettato (F4): case-insensitive.
    assert landscape_adapter_for("puglia") is PugliaPPTRClient
    assert landscape_adapter_for("PUGLIA") is PugliaPPTRClient
    assert landscape_adapter_for("sicilia") is None  # non ancora coperta
    assert landscape_adapter_for(None) is None
    assert landscape_adapter_for("") is None


def test_landscape_adapter_provider_ha_precedenza_sul_comune() -> None:
    # provider iniettato vince sulla risoluzione by-comune (anche fuori Puglia).
    assert landscape_adapter("058091", provider="puglia") is PugliaPPTRClient
    # provider sconosciuto → None anche se il comune sarebbe coperto.
    assert landscape_adapter("072021", provider="sicilia") is None


async def test_constraint_at_regione_non_coperta_none() -> None:
    # comune non pugliese → nessun adattatore → None senza toccare la rete
    assert await constraint_at(lat=41.9, lon=12.5, cod_comune="058091") is None


async def test_pptr_constraint_at_failsafe(monkeypatch) -> None:
    async def _boom(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise httpx.ConnectError("down")

    async with PugliaPPTRClient() as c:
        monkeypatch.setattr(c._client, "get", _boom)
        assert await c.constraint_at(40.99, 17.22) is None


# ── Sardegna adapter (#166): WFS PPR SITR ──────────────────────────────

from opendata_core.landscape import SardegnaPPRClient  # noqa: E402


class _FakeResp:
    def __init__(self, features: int) -> None:
        self._features = [{"id": f"x.{i}"} for i in range(features)]

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"type": "FeatureCollection", "features": self._features}


def _fake_get_by_layer(hits: dict[str, int]):
    """Fake httpx get: ritorna N feature per layer secondo `hits` (default 0)."""
    async def _get(url, params=None):  # noqa: ANN001, ANN202
        layer = (params or {}).get("typeNames", "").split(":")[-1]
        return _FakeResp(hits.get(layer, 0))
    return _get


def test_sardegna_registry_and_gate() -> None:
    # comune sardo (Cagliari 092049) → adattatore Sardegna; slug iniettato idem.
    assert landscape_adapter("092049") is SardegnaPPRClient   # Cagliari
    assert landscape_adapter("091051") is SardegnaPPRClient   # Nuoro
    assert landscape_adapter_for("sardegna") is SardegnaPPRClient
    assert landscape_adapter("072021", provider="sardegna") is SardegnaPPRClient


async def test_sardegna_coastal_hit(monkeypatch) -> None:
    async with SardegnaPPRClient() as c:
        monkeypatch.setattr(c._client, "get",
                            _fake_get_by_layer({"aree_vincolate_ex_art136": 1}))
        v = await c.constraint_at(39.205, 9.166)
    assert v is not None and v.vincolato is True
    assert "Immobili e aree di notevole interesse pubblico (art. 136)" in v.tutele
    assert v.regione == "Sardegna" and v.licenza.startswith("Regione Autonoma")


async def test_sardegna_inland_no_tutele(monkeypatch) -> None:
    async with SardegnaPPRClient() as c:
        monkeypatch.setattr(c._client, "get", _fake_get_by_layer({}))  # tutti 0
        v = await c.constraint_at(40.321, 9.330)
    assert v is not None and v.vincolato is False and v.tutele == []


async def test_sardegna_all_fail_none(monkeypatch) -> None:
    async def _boom(*_a, **_k):  # noqa: ANN002, ANN003, ANN202
        raise httpx.ReadTimeout("slow")

    async with SardegnaPPRClient() as c:
        monkeypatch.setattr(c._client, "get", _boom)
        assert await c.constraint_at(39.2, 9.1) is None  # fonte non interrogabile


async def test_sardegna_partial_fail_no_tutele_degrades_to_none(monkeypatch) -> None:
    # un layer risponde vuoto, gli altri falliscono, nessuna tutela → None (non falso negativo)
    async def _one_ok_rest_fail(url, params=None):  # noqa: ANN001, ANN202
        layer = (params or {}).get("typeNames", "").split(":")[-1]
        if layer == "aree_vincolate_ex_art136":
            return _FakeResp(0)
        raise httpx.ReadTimeout("slow")

    async with SardegnaPPRClient() as c:
        monkeypatch.setattr(c._client, "get", _one_ok_rest_fail)
        assert await c.constraint_at(39.2, 9.1) is None


# ── landscape_service_status (#168): indicatore "PPTR interrogabile?" ──


def test_service_status_covered_regions() -> None:
    p = landscape_service_status(regione="Puglia")
    assert p["queryable"] is True and p["stato"] == "interrogabile"
    assert "ArcGIS" in p["formato"] and p["provider"] == "puglia"
    s = landscape_service_status(regione="Sardegna")
    assert s["queryable"] is True and "WFS" in s["formato"]


def test_service_status_accepts_full_entity_name() -> None:
    # nomi entità reali: "Regione Puglia", "Regione Autonoma della Sardegna"
    assert landscape_service_status(regione="Regione Puglia")["provider"] == "puglia"
    assert landscape_service_status(
        regione="Regione Autonoma della Sardegna")["provider"] == "sardegna"


def test_service_status_by_provider_slug() -> None:
    assert landscape_service_status(provider="sardegna")["queryable"] is True


def test_service_status_uncovered_region_is_honest() -> None:
    r = landscape_service_status(regione="Lazio")
    assert r["queryable"] is False and r["stato"] == "non rilevato"
    assert r["formato"] is None and r["provider"] is None
    # né una regione vuota inventa copertura
    assert landscape_service_status(regione=None)["queryable"] is False
