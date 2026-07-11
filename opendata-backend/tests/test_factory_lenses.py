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
    "_resolve_istruzione", "_resolve_casa", "_resolve_reddito", "_resolve_ambiente",
    "_resolve_sanita", "_resolve_comparabili", "_resolve_aree_candidate",
    "_resolve_riconciliazione_suolo",
)


async def _pug_absent(**_kwargs) -> None:  # noqa: ANN003
    """Stub: PUG non pubblicato (evita la rete nei test della lente per i comuni pugliesi)."""
    return None


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
        "welfare", "istruzione", "casa", "reddito", "ambiente", "sanita", "comparabili", "aree",
        "suolo",
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


@pytest.mark.asyncio
async def test_resolve_comparabili_filters_scale_and_theme(monkeypatch) -> None:
    """#1 rilevanza: esclude le opere fuori scala municipale (importo > tetto) e
    limita a max 2 progetti per tema → comparabili pertinenti e diversi, non 6 strade."""
    import opendata_core.opencoesione as ocmod

    projects = [
        {"clp": "MEGA", "titolo": "Autostrada", "tema": "trasporti",
         "finanziamento_totale": 300_000_000.0, "territori": ["bari-comune"]},
        {"clp": "T1", "titolo": "Strada 1", "tema": "trasporti",
         "finanziamento_totale": 5_000_000.0, "territori": ["altamura-comune"]},
        {"clp": "T2", "titolo": "Strada 2", "tema": "trasporti",
         "finanziamento_totale": 4_000_000.0, "territori": ["bitonto-comune"]},
        {"clp": "T3", "titolo": "Strada 3", "tema": "trasporti",
         "finanziamento_totale": 3_000_000.0, "territori": ["modugno-comune"]},
        {"clp": "C1", "titolo": "Museo", "tema": "cultura e turismo",
         "finanziamento_totale": 2_000_000.0, "territori": ["bitetto-comune"]},
    ]

    class _FakeOC:
        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

        async def search_projects(self, **_):  # noqa: ANN003, ANN201
            return {"results": projects}

    monkeypatch.setattr(ocmod, "OpenCoesioneClient", _FakeOC)
    req = ProgrammaRequest(cod_comune="072021", comune_nome="Gioia del Colle", modalita="idee")
    out = await OrchestratorSession._resolve_comparabili_uncached(req)
    assert out is not None
    clps = [p["clp"] for p in out["progetti"]]
    assert "MEGA" not in clps  # fuori scala (>15M) escluso
    assert clps.count("T3") == 0  # 3° trasporti scartato (max 2 per tema)
    assert set(clps) == {"T1", "T2", "C1"}  # 2 trasporti (i più grandi) + 1 cultura


@pytest.mark.asyncio
async def test_lens_cached_force_skips_read_rewrites(monkeypatch) -> None:
    """force_refresh: `_lens_cached(force=True)` salta la lettura cache (riesegue il
    producer anche con valore in cache) e riscrive il valore fresco; force=False
    serve il valore in cache."""
    import opendata_backend.factory as fac

    calls = {"producer": 0, "set": 0}

    async def _fake_get(_key):  # noqa: ANN001, ANN202
        return "CACHED"

    async def _fake_set(_key, _val, ttl_seconds=None):  # noqa: ANN001, ANN202
        calls["set"] += 1

    async def _producer():  # noqa: ANN202
        calls["producer"] += 1
        return "FRESH"

    monkeypatch.setattr(fac, "cache_get", _fake_get)
    monkeypatch.setattr(fac, "cache_set", _fake_set)

    # force=False → serve la cache, producer non chiamato
    assert await fac._lens_cached(("x", "1"), _producer) == "CACHED"
    assert calls["producer"] == 0

    # force=True → salta la cache, riesegue il producer e riscrive
    assert await fac._lens_cached(("x", "1"), _producer, force=True) == "FRESH"
    assert calls["producer"] == 1 and calls["set"] == 1


@pytest.mark.asyncio
async def test_lens_cached_force_falls_back_to_stale_on_failure(monkeypatch) -> None:
    """force_refresh + fetch fresco fallito (None: es. ISTAT TimeoutError) → ripiega
    sul valore in cache stantio invece di perdere la lente (niente report impoverito)."""
    import opendata_backend.factory as fac

    async def _fake_get(_key):  # noqa: ANN001, ANN202
        return "STALE"

    async def _noset(_key, _val, ttl_seconds=None):  # noqa: ANN001, ANN202
        pass

    async def _failing():  # noqa: ANN202
        return None  # i resolver sono fail-safe: ritornano None su timeout

    monkeypatch.setattr(fac, "cache_get", _fake_get)
    monkeypatch.setattr(fac, "cache_set", _noset)

    # force=True ma producer fallisce → usa la cache stantia (non None)
    assert await fac._lens_cached(("x", "1"), _failing, force=True) == "STALE"


# ── Riconciliazione suolo (#127, Parte V Fase 1) ─────────────────────


@pytest.mark.asyncio
async def test_riconciliazione_suolo_failsafe(monkeypatch) -> None:
    """Fail-safe #127: aree candidate presenti ma IdroGEO e OpenCoesione entrambi
    down → la lente NON salta, produce un SoilRecord a confidenza DEGRADATA (Bassa)
    e il report sopravvive. Ogni fonte mancante degrada, non blocca."""
    import opendata_core.ispra as ispramod
    import opendata_core.opencoesione as ocmod

    async def _fake_aree(req):  # noqa: ANN001, ANN202
        return {"candidati": [
            {"osm_type": "way", "osm_id": 1, "name": "Ex scalo", "kind": "brownfield",
             "area_mq": 5000, "url": "https://osm.org/way/1"},
        ]}

    class _Down:
        async def __aenter__(self):  # noqa: ANN204
            raise RuntimeError("connector down")

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

    monkeypatch.setattr(OrchestratorSession, "_resolve_aree_candidate", staticmethod(_fake_aree))
    monkeypatch.setattr(ispramod, "IspraClient", _Down)
    monkeypatch.setattr(ispramod, "LandCoverClient", _Down)
    monkeypatch.setattr(ocmod, "OpenCoesioneClient", _Down)
    monkeypatch.setattr("opendata_core.landscape.landscape_adapter", lambda _c: None)
    monkeypatch.setattr("opendata_core.sin_sir.SinSirClient", _Down)
    monkeypatch.setattr("opendata_core.pug.fetch_zoning", _pug_absent)

    req = ProgrammaRequest(cod_comune="072021", comune_nome="Gioia del Colle", modalita="idee")
    out = await OrchestratorSession._resolve_riconciliazione_suolo_uncached(req)

    assert out is not None
    rec = out["records"][0]
    assert rec["confidenza"] == "Bassa"          # nessuna fonte ground-truth → degradata, non blocco
    assert rec["classificazione"] == "DISMESSO"
    assert rec["id_geometria"] == "way/1"


@pytest.mark.asyncio
async def test_riconciliazione_suolo_skipped_without_areas(monkeypatch) -> None:
    """Senza aree candidate (Overpass down o comune senza vuoti) la lente si salta."""
    async def _no_aree(req):  # noqa: ANN001, ANN202
        return None

    monkeypatch.setattr(OrchestratorSession, "_resolve_aree_candidate", staticmethod(_no_aree))
    req = ProgrammaRequest(cod_comune="072021", comune_nome="Gioia del Colle", modalita="idee")
    out = await OrchestratorSession._resolve_riconciliazione_suolo_uncached(req)
    assert out is None


@pytest.mark.asyncio
async def test_riconciliazione_suolo_alta_con_due_fonti(monkeypatch) -> None:
    """IdroGEO fornisce un vincolo → 2 fonti concordi (tag dismesso + vincolo) →
    confidenza Alta, classificazione VINCOLATO."""
    import opendata_core.ispra as ispramod
    import opendata_core.opencoesione as ocmod
    from opendata_core.ispra.models import HazardSlice, RiskIndicators

    async def _fake_aree(req):  # noqa: ANN001, ANN202
        return {"candidati": [
            {"osm_type": "way", "osm_id": 2, "kind": "brownfield", "area_mq": 8000},
        ]}

    class _Ispra:
        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

        async def risk_indicators(self, cod_comune):  # noqa: ANN001, ANN201
            return RiskIndicators(
                cod_comune=str(cod_comune), nome="Test",
                frane_p3p4=HazardSlice(classe="p3p4", area_pct=12.0),
                source_url="u", licenza="l",
            )

    class _OCDown:
        async def __aenter__(self):  # noqa: ANN204
            raise RuntimeError("down")

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

    monkeypatch.setattr(OrchestratorSession, "_resolve_aree_candidate", staticmethod(_fake_aree))
    monkeypatch.setattr(ispramod, "IspraClient", _Ispra)
    monkeypatch.setattr(ispramod, "LandCoverClient", _OCDown)
    monkeypatch.setattr(ocmod, "OpenCoesioneClient", _OCDown)
    monkeypatch.setattr("opendata_core.landscape.landscape_adapter", lambda _c: None)
    monkeypatch.setattr("opendata_core.sin_sir.SinSirClient", _OCDown)
    monkeypatch.setattr("opendata_core.pug.fetch_zoning", _pug_absent)

    req = ProgrammaRequest(cod_comune="072021", comune_nome="Gioia del Colle", modalita="idee")
    out = await OrchestratorSession._resolve_riconciliazione_suolo_uncached(req)
    rec = out["records"][0]
    assert rec["confidenza"] == "Alta"
    assert rec["classificazione"] == "VINCOLATO"


async def test_riconciliazione_suolo_land_cover_alza_confidenza(monkeypatch) -> None:
    """#128 Fase 2c: con IdroGEO e OpenCoesione down, la sola copertura del suolo
    (impermeabilizzato) concorda col tag OSM dismesso → 2 fonti → confidenza Alta,
    nodo 'uso reale' risolto."""
    import opendata_core.ispra as ispramod
    import opendata_core.opencoesione as ocmod
    from opendata_core.ispra.models import LandCoverInfo

    async def _fake_aree(req):  # noqa: ANN001, ANN202
        return {"candidati": [{"osm_type": "way", "osm_id": 5, "kind": "brownfield",
                               "lat": 40.79, "lon": 16.92, "area_mq": 9000}]}

    class _Down:
        async def __aenter__(self):  # noqa: ANN204
            raise RuntimeError("down")

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

    class _LC:
        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

        async def land_cover_at(self, lat, lon):  # noqa: ANN001, ANN201
            return LandCoverInfo(clc_code="111", macroclasse=1, descrizione="Superfici artificiali",
                                 impermeabilizzato=True, source_url="u", licenza="l")

    monkeypatch.setattr(OrchestratorSession, "_resolve_aree_candidate", staticmethod(_fake_aree))
    monkeypatch.setattr(ispramod, "IspraClient", _Down)
    monkeypatch.setattr(ispramod, "LandCoverClient", _LC)
    monkeypatch.setattr(ocmod, "OpenCoesioneClient", _Down)
    monkeypatch.setattr("opendata_core.sin_sir.SinSirClient", _Down)
    monkeypatch.setattr("opendata_core.pug.fetch_zoning", _pug_absent)

    # comune non pugliese → nessun adattatore paesaggistico (landscape_adapter None):
    # l'unica 2ª fonte è la copertura del suolo → basta a portare la confidenza ad Alta.
    req = ProgrammaRequest(cod_comune="058091", comune_nome="Roma", modalita="idee")
    out = await OrchestratorSession._resolve_riconciliazione_suolo_uncached(req)
    rec = out["records"][0]
    assert rec["confidenza"] == "Alta"
    assert rec["uso_reale"] != "da verificare" and "CLC" in rec["uso_reale"]


async def test_riconciliazione_suolo_vincolo_paesaggistico_alza_confidenza(monkeypatch) -> None:
    """#128 Fase 2b: con IdroGEO/OpenCoesione/copertura down, la sola tutela
    paesaggistica (PPTR) concorda col tag OSM → VINCOLATO + confidenza Alta."""
    import opendata_core.ispra as ispramod
    import opendata_core.opencoesione as ocmod
    from opendata_core.landscape.models import LandscapeConstraint

    async def _fake_aree(req):  # noqa: ANN001, ANN202
        return {"candidati": [{"osm_type": "way", "osm_id": 8, "kind": "brownfield",
                               "lat": 40.99, "lon": 17.22, "area_mq": 7000}]}

    class _Down:
        async def __aenter__(self):  # noqa: ANN204
            raise RuntimeError("down")

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

    class _PPTR:
        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

        async def constraint_at(self, lat, lon):  # noqa: ANN001, ANN201
            return LandscapeConstraint(vincolato=True, tutele=["Territori costieri"],
                                       regione="Puglia", source_url="u", licenza="l")

    monkeypatch.setattr(OrchestratorSession, "_resolve_aree_candidate", staticmethod(_fake_aree))
    monkeypatch.setattr(ispramod, "IspraClient", _Down)
    monkeypatch.setattr(ispramod, "LandCoverClient", _Down)
    monkeypatch.setattr(ocmod, "OpenCoesioneClient", _Down)
    monkeypatch.setattr("opendata_core.landscape.landscape_adapter", lambda _c: _PPTR)
    monkeypatch.setattr("opendata_core.sin_sir.SinSirClient", _Down)
    monkeypatch.setattr("opendata_core.pug.fetch_zoning", _pug_absent)

    req = ProgrammaRequest(cod_comune="072021", comune_nome="Gioia del Colle", modalita="idee")
    out = await OrchestratorSession._resolve_riconciliazione_suolo_uncached(req)
    rec = out["records"][0]
    assert rec["classificazione"] == "VINCOLATO"
    assert rec["confidenza"] == "Alta"
    assert "Territori costieri" in rec["vincoli"]


async def test_riconciliazione_suolo_contaminazione_brownfield(monkeypatch) -> None:
    """#128 Fase 2a: un sito contaminato (SIN/SIR) sul poligono dismesso → classificazione
    BROWNFIELD + confidenza Alta (OSM + contaminazione concordi)."""
    import opendata_core.ispra as ispramod
    import opendata_core.opencoesione as ocmod
    from opendata_core.sin_sir.models import ContaminationInfo

    async def _fake_aree(req):  # noqa: ANN001, ANN202
        return {"candidati": [{"osm_type": "way", "osm_id": 9, "kind": "brownfield",
                               "lat": 40.49, "lon": 17.24, "area_mq": 15000}]}

    class _Down:
        async def __aenter__(self):  # noqa: ANN204
            raise RuntimeError("down")

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

    class _SinSir:
        async def __aenter__(self):  # noqa: ANN204
            return self

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

        async def contamination_at(self, lat, lon, cod_comune):  # noqa: ANN001, ANN201
            return ContaminationInfo(contaminato=True, sin=True, sin_denominazione="70",
                                     sir_procedimenti=25, sir_contaminati=9, matrici=["SSAS"],
                                     source_url="u", licenza="l")

    monkeypatch.setattr(OrchestratorSession, "_resolve_aree_candidate", staticmethod(_fake_aree))
    monkeypatch.setattr(ispramod, "IspraClient", _Down)
    monkeypatch.setattr(ispramod, "LandCoverClient", _Down)
    monkeypatch.setattr(ocmod, "OpenCoesioneClient", _Down)
    monkeypatch.setattr("opendata_core.landscape.landscape_adapter", lambda _c: None)
    monkeypatch.setattr("opendata_core.sin_sir.SinSirClient", _SinSir)
    monkeypatch.setattr("opendata_core.pug.fetch_zoning", _pug_absent)

    req = ProgrammaRequest(cod_comune="073027", comune_nome="Taranto", modalita="idee")
    out = await OrchestratorSession._resolve_riconciliazione_suolo_uncached(req)
    rec = out["records"][0]
    assert rec["classificazione"] == "BROWNFIELD"
    assert rec["confidenza"] == "Alta"
    assert "contaminazione" in rec["causa_abbandono"]


async def test_riconciliazione_suolo_pug_risolve_destinazione(monkeypatch) -> None:
    """#129 Fase 3: PUG pubblicato come open data → destinazione_pug risolta (zona)
    e confidenza Alta (OSM + PUG concordi)."""
    import opendata_core.ispra as ispramod
    import opendata_core.opencoesione as ocmod
    from opendata_core.pug import PugZoning

    async def _fake_aree(req):  # noqa: ANN001, ANN202
        return {"candidati": [{"osm_type": "way", "osm_id": 13, "kind": "brownfield",
                               "lat": 40.8, "lon": 16.9, "area_mq": 6000}]}

    class _Down:
        async def __aenter__(self):  # noqa: ANN204
            raise RuntimeError("down")

        async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
            return False

    async def _fetch(**_k):  # noqa: ANN003
        return PugZoning(zone_key="zona", features=[], dataset_title="Zonizzazione",
                         source_url="u", licenza="CC-BY")

    monkeypatch.setattr(OrchestratorSession, "_resolve_aree_candidate", staticmethod(_fake_aree))
    monkeypatch.setattr(ispramod, "IspraClient", _Down)
    monkeypatch.setattr(ispramod, "LandCoverClient", _Down)
    monkeypatch.setattr(ocmod, "OpenCoesioneClient", _Down)
    monkeypatch.setattr("opendata_core.landscape.landscape_adapter", lambda _c: None)
    monkeypatch.setattr("opendata_core.sin_sir.SinSirClient", _Down)
    monkeypatch.setattr(
        "opendata_backend.config_files.portali_regionali",
        lambda: {"province_ckan": {"072": "https://dati.puglia.it/ckan"}},
    )
    monkeypatch.setattr("opendata_core.pug.fetch_zoning", _fetch)
    monkeypatch.setattr("opendata_core.pug.zone_at", lambda _z, _lat, _lon: "D")

    req = ProgrammaRequest(cod_comune="072021", comune_nome="Gioia del Colle", modalita="idee")
    out = await OrchestratorSession._resolve_riconciliazione_suolo_uncached(req)
    rec = out["records"][0]
    assert rec["destinazione_pug"] == "D"
    assert rec["confidenza"] == "Alta"
