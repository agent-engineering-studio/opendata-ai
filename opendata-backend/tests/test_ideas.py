"""Test Idea Lab: percorso offline deterministico, discovery, contratto report."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from opendata_backend.ideas.coach import (
    _clamp_stage,
    parse_coach_json,
    resolve_stage,
    run_chat_turn,
)
from opendata_backend.ideas.discovery import (
    build_search_query,
    discover_datasets,
    discover_funding,
    extract_keywords,
)
from opendata_backend.ideas.models import (
    STAGES,
    ChatMessage,
    FundingProject,
    IdeaChatRequest,
    IdeaDataset,
    IdeaReportRequest,
)
from opendata_backend.ideas.report import build_report, stable_idea_id


@pytest.fixture(autouse=True)
def _no_anthropic(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _settings() -> SimpleNamespace:
    # llm_provider=claude senza chiave = offline deterministico (pattern R11).
    return SimpleNamespace(
        llm_provider="claude",
        anthropic_api_key=None,
        ideas_portal_base_url=None,
        ckan_default_base_url="https://portal.example/opendata",
        ideas_portal_fq="organization:regione-puglia",
        ideas_max_datasets=8,
        ideas_max_funding=5,
        ideas_oc_cod_regione=16,
    )


def _datasets() -> list[IdeaDataset]:
    return [
        IdeaDataset(
            id="d1",
            title="Farmacie in Puglia",
            url="https://portal.example/dataset/farmacie",
            formats=["csv"],
            stars=3,
            license_open=True,
            quality_note="3/5 stelle, licenza aperta",
        ),
        IdeaDataset(
            id="d2",
            title="Strutture ospedaliere",
            url="https://portal.example/dataset/ospedali",
            formats=["pdf"],
            stars=1,
            license_open=False,
            freshness_days=800,
            quality_note="1/5 stelle, licenza da verificare",
        ),
    ]


def _funding() -> list[FundingProject]:
    return [
        FundingProject(
            clp="1BA2020",
            titolo="Telemedicina di prossimità",
            tema="inclusione-sociale",
            stato="concluso",
            ciclo="2014-2020",
            finanziamento_totale=250_000.0,
        )
    ]


# ─────────────────────────── keyword / stage ───────────────────────────


def test_extract_keywords_filters_stopwords() -> None:
    kw = extract_keywords("Vorrei migliorare l'accesso ai servizi sanitari nei piccoli comuni")
    assert "vorrei" not in kw and "servizi" in kw and "sanitari" in kw


def test_build_search_query_falls_back_to_area() -> None:
    assert build_search_query(area="salute", challenge_text="ciao a te") != ""
    q = build_search_query(area="turismo", challenge_text="")
    assert "turismo" in q


def test_resolve_and_clamp_stage() -> None:
    assert resolve_stage(None, 1) == "inquadramento"
    assert resolve_stage("divergenza", 1) == "divergenza"
    assert resolve_stage("bogus", 5) == "esplorazione"
    # mai saltare più di una tappa, mai tornare indietro
    assert _clamp_stage("esplorazione", "sintesi") == "divergenza"
    assert _clamp_stage("convergenza", "inquadramento") == "convergenza"
    assert _clamp_stage("divergenza", "not-a-stage") == "divergenza"


def test_parse_coach_json_tolerates_fences_and_truncation() -> None:
    assert parse_coach_json('```json\n{"reply": "ok"}\n```') == {"reply": "ok"}
    repaired = parse_coach_json('{"reply": "tronc')
    assert repaired is not None and "reply" in repaired
    assert parse_coach_json("non-json del tutto") is None


# ─────────────────────────── percorso offline ───────────────────────────


@pytest.mark.asyncio
async def test_offline_journey_advances_through_all_stages() -> None:
    settings = _settings()
    msgs = [ChatMessage(role="user", content="Accesso ai servizi sanitari nei piccoli comuni")]
    stage: str | None = None
    seen: list[str] = []
    for _ in range(6):
        resp = await run_chat_turn(
            settings,
            IdeaChatRequest(
                messages=msgs, area="salute", stage=stage,
                datasets=_datasets(), funding=_funding(),
            ),
        )
        assert resp.offline is True
        assert resp.stage in STAGES
        seen.append(resp.stage)
        msgs += [
            ChatMessage(role="assistant", content=resp.reply),
            ChatMessage(role="user", content="ok, avanti"),
        ]
        stage = resp.stage
    # Il primo turno apre direttamente con l'analisi dei dati (esplorazione).
    assert seen[0] == "esplorazione"
    assert seen[-1] == "sintesi"
    assert seen == sorted(seen, key=STAGES.index)  # mai indietro


@pytest.mark.asyncio
async def test_offline_first_turn_presents_data_analysis() -> None:
    """L'“Avvia l'analisi” della UI: primo messaggio → analisi con i dataset."""
    resp = await run_chat_turn(
        _settings(),
        IdeaChatRequest(
            messages=[ChatMessage(role="user", content="Monitorare le liste d'attesa")],
            area="salute",
            mode="idea",
            datasets=_datasets(),
            funding=_funding(),
        ),
    )
    assert resp.stage == "esplorazione"
    assert "Farmacie in Puglia" in resp.reply  # l'analisi cita i dataset trovati


@pytest.mark.asyncio
async def test_offline_esplorazione_cites_datasets_and_weaknesses() -> None:
    resp = await run_chat_turn(
        _settings(),
        IdeaChatRequest(
            messages=[
                ChatMessage(role="user", content="Sfida sanità territoriale"),
                ChatMessage(role="assistant", content="Qual è il problema?"),
                ChatMessage(role="user", content="Anziani senza farmacie vicine"),
            ],
            area="salute",
            stage="inquadramento",
            datasets=_datasets(),
            funding=_funding(),
        ),
    )
    assert resp.stage == "esplorazione"
    assert "Farmacie in Puglia" in resp.reply
    assert "Strutture ospedaliere" in resp.reply  # dataset debole segnalato


@pytest.mark.asyncio
async def test_sintesi_sets_report_ready() -> None:
    resp = await run_chat_turn(
        _settings(),
        IdeaChatRequest(
            messages=[ChatMessage(role="user", content="ok")],
            area="salute",
            stage="sintesi",
            datasets=_datasets(),
            funding=_funding(),
        ),
    )
    assert resp.stage == "sintesi" and resp.report_ready is True


# ─────────────────────────── discovery ───────────────────────────


class _FakeCkan:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def action(self, action: str, *, base_url: str, params: dict):
        self.calls.append({"action": action, "base_url": base_url, "params": params})
        return {
            "results": [
                {
                    "id": "abc",
                    "name": "farmacie-puglia",
                    "title": "Farmacie in Puglia",
                    "notes": "Elenco farmacie",
                    "license_id": "cc-by",
                    "isopen": True,
                    "metadata_modified": "2026-06-01T00:00:00",
                    "organization": {"title": "Regione Puglia"},
                    "resources": [{"format": "CSV", "url": "https://x/f.csv"}],
                    "tags": [{"name": "salute"}],
                }
            ]
        }


@pytest.mark.asyncio
async def test_discover_datasets_builds_quality_scored_entries() -> None:
    fake = _FakeCkan()
    found = await discover_datasets(
        _settings(),
        area="salute",
        challenge_text="farmacie di prossimità per anziani",
        client=fake,
    )
    assert len(found) == 1
    ds = found[0]
    assert ds.title == "Farmacie in Puglia"
    assert ds.stars >= 3  # CSV + licenza aperta
    assert ds.url.endswith("/dataset/farmacie-puglia")
    assert fake.calls[0]["params"]["fq"] == "organization:regione-puglia"
    assert "farmacie" in fake.calls[0]["params"]["q"]


@pytest.mark.asyncio
async def test_discover_datasets_relaxes_query_until_results() -> None:
    """q pieno → 0 risultati → si rilassa in OR e poi sulle keyword d'area."""

    class _PickyCkan(_FakeCkan):
        async def action(self, action: str, *, base_url: str, params: dict):
            resp = await super().action(action, base_url=base_url, params=params)
            # Solo la query d'area (con OR) trova qualcosa.
            if "OR" not in str(params["q"]):
                return {"results": []}
            return resp

    fake = _PickyCkan()
    found = await discover_datasets(
        _settings(),
        area="salute",
        challenge_text="farmacie e servizi sanitari nei piccoli comuni montani",
        client=fake,
    )
    assert len(found) == 1
    assert len(fake.calls) >= 2  # ha rilassato almeno una volta
    assert all(c["params"]["fq"] == "organization:regione-puglia" for c in fake.calls)


@pytest.mark.asyncio
async def test_discover_datasets_failsafe_on_error() -> None:
    class _Broken:
        async def action(self, *a, **kw):
            raise RuntimeError("network down")

    found = await discover_datasets(
        _settings(), area="salute", challenge_text="farmacie", client=_Broken()
    )
    assert found == []


class _FakeOC:
    async def search_projects(self, *, cod_regione, tema, limit):
        assert cod_regione == 16 and tema == "inclusione-sociale"
        return {
            "results": [
                {
                    "clp": "1BA2020",
                    "titolo": "Telemedicina di prossimità",
                    "tema": "inclusione-sociale",
                    "stato": "concluso",
                    "ciclo": "2014-2020",
                    "finanziamento_totale": 250000.0,
                }
            ]
        }


@pytest.mark.asyncio
async def test_discover_funding_maps_area_to_tema() -> None:
    projects = await discover_funding(_settings(), area="salute", client=_FakeOC())
    assert len(projects) == 1
    assert projects[0].finanziamento_totale == 250000.0


# ─────────────────────────── report finale ───────────────────────────


@pytest.mark.asyncio
async def test_report_offline_contract() -> None:
    resp = await build_report(
        _settings(),
        IdeaReportRequest(
            messages=[
                ChatMessage(role="user", content="Accesso ai servizi sanitari"),
                ChatMessage(role="user", content="Idea: mappa dei servizi di prossimità"),
            ],
            area="salute",
            territory="Gioia del Colle",
            datasets=_datasets(),
            funding=_funding(),
            idea_titolo="Mappa dei servizi sanitari di prossimità",
        ),
    )
    assert resp.offline is True
    md = resp.report_md
    for sezione in (
        "## In sintesi",
        "## Evidenza dai dati",
        "## Finanziabilità",
        "## Gap di dati e come colmarli",
        "## KPI e impatto",
        "## Kit di implementazione",
        "Brief di implementazione",
    ):
        assert sezione in md, f"sezione mancante: {sezione}"
    # citazioni dataset con qualità
    assert "Farmacie in Puglia" in md and "3/5" in md
    # il dataset debole genera una richiesta di miglioramento (domanda di riuso)
    assert "Strutture ospedaliere" in md and "licenza aperta" in md
    # finanziabilità dai comparabili OpenCoesione
    assert "Telemedicina di prossimità" in md and "250.000" in md
    # kit dev agent-ready ma neutro: nessuna menzione di strumenti specifici
    assert "claude" not in md.lower()
    assert "```text" in md  # brief copiabile
    # id deterministico content-hash
    assert resp.idea_id == stable_idea_id("Mappa dei servizi sanitari di prossimità")
    assert resp.idea_id.startswith("idea_") and len(resp.idea_id) == 17


def test_stable_idea_id_normalizes() -> None:
    a = stable_idea_id("Mappa dei servizi   sanitari")
    b = stable_idea_id("mappa DEI servizi sanitari ")
    assert a == b


def test_is_open_license_rejects_nc_nd_variants() -> None:
    from opendata_core.maturity.models import is_open_license

    # NC/ND non sono aperte, nemmeno se il portale dice isopen=True
    assert is_open_license("cc-by-nc-4.0", None, True) is False
    assert is_open_license(None, "CC BY-NC-ND 4.0", False) is False
    assert is_open_license(None, "Creative Commons Attribuzione - Non commerciale", None) is False
    # le CC BY federate con isopen=False restano aperte (euristica)
    assert is_open_license("Creative Commons Attribuzione 4.0 (CC BY 4.0)", None, False) is True


@pytest.mark.asyncio
async def test_report_survives_partial_llm_json(monkeypatch) -> None:
    """JSON LLM con solo 'titolo': i campi mancanti vengono dai default, no KeyError."""
    from opendata_backend.ideas import report as report_mod

    async def _fake_complete(settings, **kwargs):
        return '{"titolo": "Solo titolo dal modello"}'

    monkeypatch.setattr(report_mod, "complete", _fake_complete)
    resp = await build_report(
        _settings(),
        IdeaReportRequest(
            messages=[ChatMessage(role="user", content="sfida rifiuti")],
            area="ambiente",
            datasets=_datasets(),
            funding=_funding(),
        ),
    )
    assert resp.offline is False
    assert resp.titolo == "Solo titolo dal modello"
    assert "## In sintesi" in resp.report_md  # problema/beneficiari dai default


@pytest.mark.asyncio
async def test_coach_unparsable_llm_does_not_advance_stage(monkeypatch) -> None:
    from opendata_backend.ideas import coach as coach_mod

    async def _fake_complete(settings, **kwargs):
        return "risposta in prosa, niente JSON qui"

    monkeypatch.setattr(coach_mod, "complete", _fake_complete)
    resp = await run_chat_turn(
        _settings(),
        IdeaChatRequest(
            messages=[
                ChatMessage(role="user", content="sfida"),
                ChatMessage(role="assistant", content="domanda"),
                ChatMessage(role="user", content="risposta"),
            ],
            area="salute",
            stage="divergenza",
            datasets=_datasets(),
            funding=_funding(),
        ),
    )
    assert resp.stage == "divergenza"  # nessun avanzamento silenzioso
    assert resp.offline is True


def test_agent_card_publishes_idea_lab_skill() -> None:
    from opendata_backend.a2a.agent_card import SKILL_IDEAS, build_agent_card

    card = build_agent_card("http://localhost:18000")
    ids = [s.id for s in card.skills]
    assert SKILL_IDEAS in ids
