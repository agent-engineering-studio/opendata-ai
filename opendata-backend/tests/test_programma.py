"""Tests for the evidence-based programma aggregator + deterministic guardrails.

The LLM is stubbed: what's under test is the boundary that must hold — the
evidence bundle fed to the agent, the JSON parsing, and above all the
guardrails (orphan claims dropped, unfunded proposals degraded, persuasive
language removed, disclaimer guaranteed).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from opendata_backend.orchestrator.guardrails import DEFAULT_DISCLAIMER, validate_programma
from opendata_backend.orchestrator.programma import (
    Evidenza,
    Fattibilita,
    Finanziamento,
    ProgrammaRequest,
    ProgrammaResponse,
    Proposta,
    VoceSwot,
    build_programma_aggregator,
    build_programma_task,
)

# ───────────────────────────── stubs ─────────────────────────────


@dataclass
class _StubAgentResponse:
    text: str


class _StubProgrammaAgent:
    def __init__(self, canned: str) -> None:
        self.canned = canned
        self.last_prompt: str | None = None

    async def run(self, prompt: str) -> _StubAgentResponse:
        self.last_prompt = prompt
        return _StubAgentResponse(text=self.canned)


class _FakeStream:
    """Mima `ResponseStream`: async-iterabile di update + get_final_response()."""

    def __init__(self, deltas: list[str], final: str) -> None:
        self._deltas = deltas
        self._final = final

    def __aiter__(self):  # noqa: ANN204
        return self._gen()

    async def _gen(self):  # noqa: ANN202
        for d in self._deltas:
            yield _StubAgentResponse(text=d)

    async def get_final_response(self) -> _StubAgentResponse:
        return _StubAgentResponse(text=self._final)


class _StreamingStubAgent:
    """Agente che supporta `run(prompt, stream=True)` → _FakeStream (per L3)."""

    def __init__(self, canned: str) -> None:
        self.canned = canned

    def run(self, prompt: str, stream: bool = False):  # noqa: ANN201
        if stream:
            mid = max(1, len(self.canned) // 2)
            return _FakeStream([self.canned[:mid], self.canned[mid:]], self.canned)

        async def _coro() -> _StubAgentResponse:
            return _StubAgentResponse(text=self.canned)

        return _coro()


@dataclass
class _StubInnerResponse:
    text: str


@dataclass
class _StubResult:
    executor_id: str
    agent_response: _StubInnerResponse


def _participant(executor_id: str, narrative: str, resources: list[dict[str, Any]]) -> _StubResult:
    raw = (
        f"{narrative}\n<!--RESOURCES_JSON-->\n{json.dumps(resources)}\n<!--/RESOURCES_JSON-->"
    )
    return _StubResult(executor_id=executor_id, agent_response=_StubInnerResponse(text=raw))


_OC_URL = "https://opencoesione.gov.it/it/api/aggregati/territori/barletta-comune.json"
_ISTAT_URL = "https://esploradati.istat.it/SDMXWS/rest/data/POPRES1/all"
_REQ = ProgrammaRequest(cod_comune="110002", zona="area industriale", tema="energia")


def _participants() -> list[_StubResult]:
    return [
        _participant(
            "opencoesione",
            "A Barletta 2616 progetti, spend ratio 0.38.",
            [{"name": "capacità di spesa Barletta", "url": _OC_URL, "format": "JSON", "content": None}],
        ),
        _participant(
            "istat",
            "Popolazione residente 92.627 (2025).",
            [{"name": "POPRES1", "url": _ISTAT_URL, "format": "CSV", "content": None}],
        ),
    ]


def _voce(testo: str, url: str = _OC_URL, fonte: str = "opencoesione") -> dict[str, Any]:
    return {"testo": testo, "evidenze": [{"fonte": fonte, "url": url, "dettaglio": "dato"}]}


def _llm_json(**overrides: Any) -> str:
    base: dict[str, Any] = {
        "swot": {
            "forze": [_voce("Spend ratio nella media (0.38).")],
            "debolezze": [],
            "opportunita": [_voce("Popolazione stabile.", _ISTAT_URL, "istat")],
            "minacce": [],
        },
        "proposte": [
            {
                "titolo": "Efficientamento energetico zona PIP",
                "descrizione": "Intervento sugli immobili produttivi.",
                "evidenze": [{"fonte": "opencoesione", "url": _OC_URL, "dettaglio": "ratio 0.38"}],
                "finanziamento": None,
                "fattibilita": {"livello": "alta", "motivazione": "ratio ok",
                                "spend_ratio_storico": 0.38},
            }
        ],
        "disclaimer": "Analisi automatica su dati pubblici.",
    }
    base.update(overrides)
    return json.dumps(base, ensure_ascii=False)


# ───────────────────────────── aggregator ─────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_builds_validated_response() -> None:
    agent = _StubProgrammaAgent(_llm_json())
    aggregate = build_programma_aggregator(agent, _REQ)  # type: ignore[arg-type]

    out = await aggregate(_participants())
    resp = out.response
    assert isinstance(resp, ProgrammaResponse)
    assert resp.comune == "110002" and resp.zona == "area industriale"
    assert set(resp.swot.keys()) == {"forze", "debolezze", "opportunita", "minacce"}
    assert len(resp.swot["forze"]) == 1
    assert len(resp.proposte) == 1
    # Proposta senza finanziamento → fattibilità degradata dal guardrail.
    assert resp.proposte[0].fattibilita.livello == "da_verificare"
    # citazioni display-clean: file/API → sito di origine (mai il link profondo).
    assert {r.url for r in resp.citazioni} == {
        "https://opencoesione.gov.it/", "https://www.istat.it/"
    }
    assert resp.disclaimer
    # Il wrapper espone anche il JSON serializzato per events.get_outputs().
    assert json.loads(out.text)["comune"] == "110002"
    assert out.evidence_sources == ["istat", "opencoesione"]

    # Il prompt al programma_agent contiene richiesta, sezioni e risorse citabili.
    prompt = agent.last_prompt or ""
    assert "RICHIESTA:" in prompt and "comune ISTAT: 110002" in prompt
    assert "=== OPENCOESIONE ===" in prompt and "=== ISTAT ===" in prompt
    assert _OC_URL in prompt and "RISORSE CITABILI" in prompt


@pytest.mark.asyncio
async def test_synthesis_streams_thinking_events_when_emit_provided() -> None:
    """L3: con `emit`, la sintesi STREAMA i token (eventi 'thinking' + status
    start/end della fase). Senza emit resta una run non-streaming (altri test)."""
    events: list[dict[str, Any]] = []
    agent = _StreamingStubAgent(_llm_json())
    aggregate = build_programma_aggregator(agent, _REQ)  # type: ignore[arg-type]

    out = await aggregate(_participants(), emit=events.append)
    assert out.response is not None and len(out.response.proposte) == 1  # sintesi valida
    assert any(e["event"] == "thinking" and e.get("delta") for e in events)  # token live
    assert any(e["event"] == "status" and e["phase"] == "start" for e in events)
    assert any(e["event"] == "status" and e["phase"] == "end" for e in events)


@pytest.mark.asyncio
async def test_orphan_claims_are_dropped() -> None:
    """Voci/proposte con URL mai raccolti dagli specialisti vengono scartate."""
    fake = "https://example.org/inventato.json"
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={
                "forze": [_voce("Claim fondato.")],
                "debolezze": [_voce("Claim inventato.", fake)],
                "opportunita": [],
                "minacce": [],
            },
            proposte=[
                {
                    "titolo": "Proposta orfana",
                    "descrizione": "Nessuna fonte vera.",
                    "evidenze": [{"fonte": "ckan", "url": fake, "dettaglio": "x"}],
                    "finanziamento": None,
                    "fattibilita": {"livello": "media", "motivazione": "m",
                                    "spend_ratio_storico": None},
                }
            ],
        )
    )
    aggregate = build_programma_aggregator(agent, _REQ)  # type: ignore[arg-type]
    resp = (await aggregate(_participants())).response
    assert resp is not None
    assert len(resp.swot["forze"]) == 1
    assert resp.swot["debolezze"] == []  # orfana → scartata
    assert resp.proposte == []  # orfana → scartata


@pytest.mark.asyncio
async def test_unresolvable_funding_is_stripped_and_degraded() -> None:
    agent = _StubProgrammaAgent(
        _llm_json(
            proposte=[
                {
                    "titolo": "Proposta con finanziamento inventato",
                    "descrizione": "d",
                    "evidenze": [{"fonte": "opencoesione", "url": _OC_URL, "dettaglio": "x"}],
                    "finanziamento": {"linea": "PR FESR", "fonte_url": "https://example.org/fake",
                                      "stato": "aperto"},
                    "fattibilita": {"livello": "alta", "motivazione": "m",
                                    "spend_ratio_storico": 0.5},
                }
            ]
        )
    )
    aggregate = build_programma_aggregator(agent, _REQ)  # type: ignore[arg-type]
    resp = (await aggregate(_participants())).response
    assert resp is not None and len(resp.proposte) == 1
    prop = resp.proposte[0]
    assert prop.finanziamento is None
    assert prop.fattibilita.livello == "da_verificare"


@pytest.mark.asyncio
async def test_persuasive_language_is_removed() -> None:
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={
                "forze": [_voce("Votate per il cambiamento, risultati straordinari!")],
                "debolezze": [],
                "opportunita": [_voce("Dato sobrio e fondato.")],
                "minacce": [],
            },
            proposte=[
                {
                    "titolo": "Insieme possiamo rivoluzionare la città",
                    "descrizione": "Promettiamo il futuro.",
                    "evidenze": [{"fonte": "opencoesione", "url": _OC_URL, "dettaglio": "x"}],
                    "finanziamento": None,
                    "fattibilita": {"livello": "alta", "motivazione": "m",
                                    "spend_ratio_storico": None},
                }
            ],
        )
    )
    aggregate = build_programma_aggregator(agent, _REQ)  # type: ignore[arg-type]
    resp = (await aggregate(_participants())).response
    assert resp is not None
    assert resp.swot["forze"] == []  # "Votate" + "straordinari" → rimossa
    assert len(resp.swot["opportunita"]) == 1
    assert resp.proposte == []  # "Insieme possiamo" / "Promettiamo" → rimossa


@pytest.mark.asyncio
async def test_missing_disclaimer_is_injected_and_garbage_llm_is_safe() -> None:
    agent = _StubProgrammaAgent("non sono affatto un JSON")
    aggregate = build_programma_aggregator(agent, _REQ)  # type: ignore[arg-type]
    resp = (await aggregate(_participants())).response
    assert resp is not None
    assert resp.disclaimer == DEFAULT_DISCLAIMER
    assert resp.proposte == [] and all(v == [] for v in resp.swot.values())
    # Le citazioni raccolte restano disponibili anche con scheda vuota.
    assert len(resp.citazioni) == 2


@pytest.mark.asyncio
async def test_llm_json_inside_markdown_fence_is_parsed() -> None:
    agent = _StubProgrammaAgent("Ecco la scheda:\n```json\n" + _llm_json() + "\n```")
    aggregate = build_programma_aggregator(agent, _REQ)  # type: ignore[arg-type]
    resp = (await aggregate(_participants())).response
    assert resp is not None and len(resp.swot["forze"]) == 1


# ───────────────────────────── guardrails unit ─────────────────────────────


def _resp(proposte: list[Proposta], disclaimer: str = "ok") -> ProgrammaResponse:
    from datetime import datetime, timezone

    return ProgrammaResponse(
        comune="110002",
        swot={k: [] for k in ("forze", "debolezze", "opportunita", "minacce")},
        proposte=proposte,
        citazioni=[],
        disclaimer=disclaimer,
        generato_il=datetime.now(timezone.utc),
    )


def test_validate_keeps_funded_proposal_level() -> None:
    prop = Proposta(
        titolo="Con finanziamento vero",
        descrizione="d",
        evidenze=[Evidenza(fonte="opencoesione", url=_OC_URL, dettaglio="x")],
        finanziamento=Finanziamento(linea="PR FESR Puglia", fonte_url=_OC_URL, stato="aperto"),
        fattibilita=Fattibilita(livello="alta", motivazione="m", spend_ratio_storico=0.8),
    )
    out = validate_programma(_resp([prop]), {_OC_URL})
    assert out.proposte[0].fattibilita.livello == "alta"
    assert out.proposte[0].finanziamento is not None


def test_validate_task_builder_mentions_zona_and_tema() -> None:
    task = build_programma_task(_REQ)
    assert "110002" in task and "area industriale" in task and "energia" in task


def test_voce_swot_model_requires_evidence_shape() -> None:
    v = VoceSwot(testo="t", evidenze=[Evidenza(fonte="istat", url="https://x", dettaglio="d")])
    assert v.evidenze[0].fonte == "istat"


@pytest.mark.asyncio
async def test_malformed_voce_does_not_nuke_the_scheda() -> None:
    """Regressione smoke 7B: un typo del modello (fonte mancante/struttura
    rotta) scarta LA VOCE, non l'intera scheda; i tag fonte sono normalizzati."""
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={
                "forze": [_voce("Voce buona.")],
                "debolezze": [{"testo": "Voce rotta", "evidenze": "non-una-lista"}],
                "opportunita": [
                    {"testo": "Tag con typo ok", "evidenze": [
                        {"fonte": "  ISPRA ", "url": _OC_URL, "dettaglio": "x"}
                    ]}
                ],
                "minacce": [],
            }
        )
    )
    aggregate = build_programma_aggregator(agent, _REQ)  # type: ignore[arg-type]
    resp = (await aggregate(_participants())).response
    assert resp is not None
    assert len(resp.swot["forze"]) == 1          # sopravvive
    assert resp.swot["debolezze"] == []          # solo la voce rotta scartata
    assert len(resp.swot["opportunita"]) == 1
    assert resp.swot["opportunita"][0].evidenze[0].fonte == "ispra"  # normalizzato


@pytest.mark.asyncio
async def test_duplicate_tool_citations_are_deduped() -> None:
    """Due chiamate allo stesso tool → UNA citazione (regressione smoke 7B)."""
    agent = _StubProgrammaAgent(_llm_json())
    aggregate = build_programma_aggregator(agent, _REQ)  # type: ignore[arg-type]

    # Partecipante che ha citato la stessa risorsa due volte nel blocco.
    dup = _participant(
        "opencoesione",
        "Narrativa.",
        [
            {"name": "capacità di spesa", "url": _OC_URL, "format": "JSON", "content": None},
            {"name": "capacità di spesa (bis)", "url": _OC_URL, "format": "JSON", "content": None},
        ],
    )
    resp = (await aggregate([dup, _participants()[1]])).response
    assert resp is not None
    assert [r.url for r in resp.citazioni].count("https://opencoesione.gov.it/") == 1


# ───────────────────────── modalità idee (Pezzo 8) ─────────────────────────

_AGG_URL = "https://opencoesione.gov.it/it/api/aggregati/territori/barletta-comune.json"
_SEARCH_URL = (
    "https://opencoesione.gov.it/it/api/progetti.json?territorio=barletta-comune"
)
#: URL di PROGETTO SPECIFICO — richiesto da gap_comparativo/incompiuto.
_PROJ_URL = "https://opencoesione.gov.it/it/api/progetti/peer1clp.json"
_IDEE_REQ = ProgrammaRequest(cod_comune="110002", comune_nome="Barletta", modalita="idee")


def _idea(generatore: str | None, evidenze: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "titolo": f"Idea {generatore}",
        "descrizione": "d",
        "generatore": generatore,
        "evidenze": evidenze,
        "finanziamento": None,
        "fattibilita": {"livello": "media", "motivazione": "m", "spend_ratio_storico": None},
    }


@pytest.mark.asyncio
async def test_idee_mode_enforces_generator_premises() -> None:
    """Per generatore: premesse minime o la proposta è SCARTATA (non degradata)."""
    # gap_comparativo/incompiuto esigono il link al PROGETTO SPECIFICO
    # (/api/progetti/{clp}); la ricerca generica non basta più.
    ev_proj = {"fonte": "opencoesione", "url": _PROJ_URL, "dettaglio": "x"}
    ev_search = {"fonte": "opencoesione", "url": _SEARCH_URL, "dettaglio": "x"}
    ev_agg = {"fonte": "opencoesione", "url": _AGG_URL, "dettaglio": "x"}
    ev_istat = {"fonte": "istat", "url": _ISTAT_URL, "dettaglio": "x"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[
                _idea("gap_comparativo", [ev_proj]),             # ok (progetto specifico)
                _idea("gap_comparativo", [ev_search]),           # solo ricerca → out
                _idea("fabbisogno", [ev_istat, ev_search]),      # ok (indicatore + locale)
                _idea("fabbisogno", [ev_istat]),                 # manca la ricerca locale → out
                _idea("incompiuto", [ev_proj]),                  # ok
                _idea("finestra_finanziamento", [ev_agg]),       # ok (aggregati)
                _idea("finestra_finanziamento", [ev_search]),    # non è un URL aggregati → out
                _idea(None, [ev_proj]),                          # senza generatore → out
                _idea("GAP_COMPARATIVO ", [ev_proj]),            # normalizzato → ok
            ],
        )
    )
    parts = _participants()
    parts[0] = _participant(
        "opencoesione",
        "Narrativa.",
        [
            {"name": "progetto peer", "url": _PROJ_URL, "format": "JSON", "content": None},
            {"name": "ricerca", "url": _SEARCH_URL, "format": "JSON", "content": None},
            {"name": "aggregati", "url": _AGG_URL, "format": "JSON", "content": None},
        ],
    )
    aggregate = build_programma_aggregator(agent, _IDEE_REQ)  # type: ignore[arg-type]
    resp = (await aggregate(parts)).response
    assert resp is not None
    generatori = [p.generatore for p in resp.proposte]
    assert generatori == [
        "gap_comparativo", "fabbisogno", "incompiuto",
        "finestra_finanziamento", "gap_comparativo",
    ]


@pytest.mark.asyncio
async def test_commercio_duc_requires_local_indicator() -> None:
    """commercio_duc (lente Commercio): premessa = indicatore ISTAT o densità OSM
    (host in _INDICATORE_HOSTS); nessun requisito web. Solo OpenCoesione → out."""
    osm_url = "https://www.openstreetmap.org/#map=15/40.79800/16.92300"
    ispra_url = "https://idrogeo.isprambiente.it/api/pir/comuni/72021"
    ev_istat = {"fonte": "istat", "url": _ISTAT_URL, "dettaglio": "120 imprese attive"}
    ev_osm = {"fonte": "osm", "url": osm_url, "dettaglio": "densità commercio: 8 negozi"}
    ev_oc = {"fonte": "opencoesione", "url": _OC_URL, "dettaglio": "x"}
    ev_ispra = {"fonte": "ispra", "url": ispra_url, "dettaglio": "frane"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[
                _idea("commercio_duc", [ev_istat]),   # ok (indicatore ISTAT)
                _idea("commercio_duc", [ev_osm]),     # ok (densità OSM)
                _idea("commercio_duc", [ev_oc]),      # solo OpenCoesione → out
                _idea("commercio_duc", [ev_ispra]),   # ISPRA (ambiente) → out
            ],
        )
    )
    parts = _participants()
    parts[0] = _participant(
        "osm", "Densità.",
        [
            {"name": "imprese", "url": _ISTAT_URL, "format": "JSON", "content": None},
            {"name": "profilo commercio", "url": osm_url, "format": "JSON", "content": None},
            {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
            {"name": "rischio", "url": ispra_url, "format": "JSON", "content": None},
        ],
    )
    aggregate = build_programma_aggregator(agent, _IDEE_REQ)  # type: ignore[arg-type]
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["commercio_duc", "commercio_duc"]


@pytest.mark.asyncio
async def test_commercio_info_injects_citable_istat_anchor() -> None:
    """L'ancora commercio deterministica (ISTAT ASIA iniettata dal backend) rende
    citabile la fonte: una proposta commercio_duc che la cita sopravvive ANCHE se
    nessuno specialista ha prodotto una risorsa ISTAT. È il fix che rende la lente
    non-dormiente (l'agente ISTAT LLM non faceva emergere il dato)."""
    asia_url = (
        "https://esploradati.istat.it/SDMXWS/rest/data/183_285/A.110002...TOTAL"
        "?startPeriod=2020"
    )
    commercio_info = {
        "trovato": True,
        "anno": "2023",
        "totale": {"unita_locali": 2056, "addetti": 6048.3},
        "commercio": {
            "ateco": "G",
            "unita_locali": 569,
            "addetti": 1473.6,
            "quota_unita_locali_pct": 27.7,
        },
        "source_url": asia_url,
    }
    ev_asia = {"fonte": "istat", "url": asia_url, "dettaglio": "569 UL commercio (sez. G)"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[_idea("commercio_duc", [ev_asia])],
        )
    )
    # Specialisti SENZA alcuna risorsa ISTAT: l'unica citazione valida è l'ancora iniettata.
    parts = [_participant("opencoesione", "Narrativa.", [
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])]
    aggregate = build_programma_aggregator(
        agent, _IDEE_REQ, commercio_info=commercio_info  # type: ignore[arg-type]
    )
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["commercio_duc"]
    # la fonte ISTAT ASIA è citabile (validata sull'URL grezzo) e in display
    # compare come sito di origine ISTAT (mai il link SDMX profondo).
    assert any(r.url == "https://www.istat.it/" for r in resp.citazioni)


@pytest.mark.asyncio
async def test_turismo_cultura_requires_local_anchor() -> None:
    """turismo_cultura (lente Turismo): premessa = asset OSM o ricettività ISTAT
    (host in _TURISMO_HOSTS); nessun requisito web. Solo OpenCoesione → out."""
    osm_url = "https://www.openstreetmap.org/#map=13/40.79800/16.92300"
    ev_osm = {"fonte": "osm", "url": osm_url, "dettaglio": "12 musei, Castello X"}
    ev_istat = {"fonte": "istat", "url": _ISTAT_URL, "dettaglio": "posti letto"}
    ev_oc = {"fonte": "opencoesione", "url": _OC_URL, "dettaglio": "x"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[
                _idea("turismo_cultura", [ev_osm]),    # ok (asset OSM)
                _idea("turismo_cultura", [ev_istat]),  # ok (ricettività ISTAT)
                _idea("turismo_cultura", [ev_oc]),     # solo OpenCoesione → out
            ],
        )
    )
    parts = _participants()
    parts[0] = _participant("osm", "Asset.", [
        {"name": "asset turistici", "url": osm_url, "format": "JSON", "content": None},
        {"name": "ricettività", "url": _ISTAT_URL, "format": "JSON", "content": None},
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])
    aggregate = build_programma_aggregator(agent, _IDEE_REQ)  # type: ignore[arg-type]
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["turismo_cultura", "turismo_cultura"]


@pytest.mark.asyncio
async def test_turismo_info_injects_citable_osm_anchor() -> None:
    """L'ancora turismo deterministica (asset OSM iniettati dal backend) rende
    citabile la fonte: una proposta turismo_cultura che la cita sopravvive ANCHE
    se nessuno specialista ha prodotto la risorsa OSM."""
    osm_url = "https://www.openstreetmap.org/#map=13/40.79800/16.92300"
    turismo_info = {
        "comune": "110002",
        "counts": {"musei": 2, "monumenti_siti": 5, "attrazioni": 3, "ricettivita": 7, "cultura": 1},
        "landmarks": [{"name": "Castello Svevo", "kind": "castle"}],
        "source_url": osm_url,
    }
    ev_osm = {"fonte": "osm", "url": osm_url, "dettaglio": "5 monumenti, Castello Svevo"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[_idea("turismo_cultura", [ev_osm])],
        )
    )
    parts = [_participant("opencoesione", "Narrativa.", [
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])]
    aggregate = build_programma_aggregator(
        agent, _IDEE_REQ, turismo_info=turismo_info  # type: ignore[arg-type]
    )
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["turismo_cultura"]
    # OSM resta àncora di validazione (la proposta sopravvive) ma è NASCOSTA dalle
    # fonti display: la mappa mostra già il dettaglio, il link OSM è inutile.
    assert not any("openstreetmap.org" in r.url for r in resp.citazioni)


@pytest.mark.asyncio
async def test_turismo_info_injects_citable_istat_ricettivita_anchor() -> None:
    """L'ancora ricettività ISTAT (posti letto/esercizi) iniettata dal backend è
    citabile: una proposta turismo_cultura che cita il source_url ISTAT sopravvive
    anche SENZA asset OSM (es. Overpass giù) — è l'ancora affidabile della Fase B."""
    istat_url = (
        "https://esploradati.istat.it/SDMXWS/rest/data/122_54/A.072021...ALL......TOT"
        "?startPeriod=2021"
    )
    turismo_info = {
        "comune": "110002",
        # nessun blocco OSM (counts/source_url assenti) → solo l'ancora ISTAT
        "ricettivita": {
            "anno": "2024", "posti_letto": 570, "esercizi": 40, "camere": 138,
            "source_url": istat_url,
        },
    }
    ev_istat = {"fonte": "istat", "url": istat_url, "dettaglio": "570 posti letto, 40 esercizi"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[_idea("turismo_cultura", [ev_istat])],
        )
    )
    parts = [_participant("opencoesione", "Narrativa.", [
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])]
    aggregate = build_programma_aggregator(
        agent, _IDEE_REQ, turismo_info=turismo_info  # type: ignore[arg-type]
    )
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["turismo_cultura"]
    # ricettività ISTAT in display = sito di origine ISTAT (mai il link SDMX).
    assert any(r.url == "https://www.istat.it/" for r in resp.citazioni)


@pytest.mark.asyncio
async def test_lavoro_requires_local_anchor() -> None:
    """lavoro (lente Lavoro): premessa = indicatori ISTAT 8milaCensus (host in
    _LAVORO_HOSTS). Solo OpenCoesione → out; nessun requisito web."""
    census_url = "https://ottomilacensus.istat.it/fileadmin/download/16/confini/confini_16.csv"
    ev_census = {"fonte": "istat", "url": census_url, "dettaglio": "disocc. giovanile 36,5% (Cens. 2011)"}
    ev_oc = {"fonte": "opencoesione", "url": _OC_URL, "dettaglio": "x"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[
                _idea("lavoro", [ev_census]),  # ok (8milaCensus)
                _idea("lavoro", [ev_oc]),      # solo OpenCoesione → out
            ],
        )
    )
    parts = _participants()
    parts[0] = _participant("istat", "Lavoro.", [
        {"name": "8milaCensus", "url": census_url, "format": "CSV", "content": None},
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])
    aggregate = build_programma_aggregator(agent, _IDEE_REQ)  # type: ignore[arg-type]
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["lavoro"]


@pytest.mark.asyncio
async def test_lavoro_info_injects_citable_census_anchor() -> None:
    """L'ancora Lavoro deterministica (8milaCensus) iniettata dal backend è citabile:
    una proposta lavoro che la cita sopravvive anche senza risorsa ISTAT dagli specialisti."""
    census_url = "https://ottomilacensus.istat.it/fileadmin/download/16/confini/confini_16.csv"
    lavoro_info = {
        "comune": "110002", "anno": "2011",
        "tasso_occupazione": 39.6, "tasso_disoccupazione": 13.5,
        "tasso_disoccupazione_giovanile": 36.5, "neet_15_29": 23.4, "tasso_attivita": 45.8,
        "settori": {"agricolo": 12.4, "industriale": 22.0, "terziario_extracommercio": 47.7, "commercio": 17.9},
        "source_url": census_url,
    }
    ev_census = {"fonte": "istat", "url": census_url, "dettaglio": "NEET 23,4% (Censimento 2011)"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[_idea("lavoro", [ev_census])],
        )
    )
    parts = [_participant("opencoesione", "Narrativa.", [
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])]
    aggregate = build_programma_aggregator(
        agent, _IDEE_REQ, lavoro_info=lavoro_info  # type: ignore[arg-type]
    )
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["lavoro"]
    # 8milaCensus in display = sito di origine ISTAT (mai il CSV profondo).
    assert any(r.url == "https://www.istat.it/" for r in resp.citazioni)


@pytest.mark.asyncio
async def test_trasporti_requires_local_anchor() -> None:
    """trasporti (lente Trasporti): premessa = densità OSM public-transport (host in
    _TRASPORTI_HOSTS). Solo OpenCoesione → out; nessun requisito web."""
    osm_url = "https://www.openstreetmap.org/#map=13/40.79800/16.92300"
    ev_osm = {"fonte": "osm", "url": osm_url, "dettaglio": "40 fermate, 1 stazione"}
    ev_oc = {"fonte": "opencoesione", "url": _OC_URL, "dettaglio": "x"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[
                _idea("trasporti", [ev_osm]),  # ok (OSM)
                _idea("trasporti", [ev_oc]),   # solo OpenCoesione → out
            ],
        )
    )
    parts = _participants()
    parts[0] = _participant("osm", "TPL.", [
        {"name": "trasporti", "url": osm_url, "format": "JSON", "content": None},
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])
    aggregate = build_programma_aggregator(agent, _IDEE_REQ)  # type: ignore[arg-type]
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["trasporti"]


@pytest.mark.asyncio
async def test_trasporti_info_injects_citable_osm_anchor() -> None:
    """L'ancora Trasporti deterministica (OSM) iniettata dal backend è citabile:
    una proposta trasporti che la cita sopravvive senza risorsa OSM dagli specialisti."""
    osm_url = "https://www.openstreetmap.org/#map=13/40.79800/16.92300"
    trasporti_info = {
        "comune": "110002",
        "counts": {"fermate_bus": 40, "autostazioni": 2, "stazioni_treno": 1, "tram_metro": 0},
        "ha_stazione_treno": True,
        "source_url": osm_url,
    }
    ev_osm = {"fonte": "osm", "url": osm_url, "dettaglio": "40 fermate bus, 1 stazione"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[_idea("trasporti", [ev_osm])],
        )
    )
    parts = [_participant("opencoesione", "Narrativa.", [
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])]
    aggregate = build_programma_aggregator(
        agent, _IDEE_REQ, trasporti_info=trasporti_info  # type: ignore[arg-type]
    )
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["trasporti"]
    # Trasporti resta valido (àncora OSM grezza), ma OSM è NASCOSTO dalle fonti
    # display: la lente vive "ancorata alla mappa, non a un link".
    assert not any("openstreetmap.org" in r.url for r in resp.citazioni)


@pytest.mark.asyncio
async def test_welfare_requires_local_anchor() -> None:
    """welfare (lente Welfare): premessa = indici demografici ISTAT DCIS_POPRES1
    (host in _WELFARE_HOSTS). Solo OpenCoesione → out; nessun requisito web."""
    pop_url = (
        "https://esploradati.istat.it/SDMXWS/rest/data/22_289/A.110002.JAN..9.99"
        "?startPeriod=2020"
    )
    ev_pop = {"fonte": "istat", "url": pop_url, "dettaglio": "indice vecchiaia 248"}
    ev_oc = {"fonte": "opencoesione", "url": _OC_URL, "dettaglio": "x"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[
                _idea("welfare", [ev_pop]),  # ok (ISTAT popolazione)
                _idea("welfare", [ev_oc]),   # solo OpenCoesione → out
            ],
        )
    )
    parts = _participants()
    parts[0] = _participant("istat", "Demografia.", [
        {"name": "popolazione", "url": pop_url, "format": "CSV", "content": None},
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])
    aggregate = build_programma_aggregator(agent, _IDEE_REQ)  # type: ignore[arg-type]
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["welfare"]


@pytest.mark.asyncio
async def test_welfare_info_injects_citable_istat_anchor() -> None:
    """L'ancora Welfare deterministica (indici demografici ISTAT) iniettata dal backend
    è citabile: una proposta welfare che la cita sopravvive senza risorsa ISTAT dagli
    specialisti."""
    pop_url = (
        "https://esploradati.istat.it/SDMXWS/rest/data/22_289/A.110002.JAN..9.99"
        "?startPeriod=2020"
    )
    welfare_info = {
        "comune": "110002", "anno": "2023", "popolazione": 27000,
        "indice_vecchiaia": 248.3, "indice_dipendenza_anziani": 41.2,
        "indice_dipendenza_strutturale": 58.0, "pct_over_65": 26.0, "pct_under_15": 10.5,
        "source_url": pop_url,
    }
    ev_pop = {"fonte": "istat", "url": pop_url, "dettaglio": "indice vecchiaia 248,3"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[_idea("welfare", [ev_pop])],
        )
    )
    parts = [_participant("opencoesione", "Narrativa.", [
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])]
    aggregate = build_programma_aggregator(
        agent, _IDEE_REQ, welfare_info=welfare_info  # type: ignore[arg-type]
    )
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["welfare"]
    # display-clean: la fonte ISTAT compare come sito di origine (mai il link SDMX).
    assert any(r.url == "https://www.istat.it/" for r in resp.citazioni)


@pytest.mark.asyncio
async def test_welfare_info_social_investments_are_citable() -> None:
    """Arricchimento Fase A: gli investimenti OpenCoesione 'inclusione-sociale'
    iniettati con welfare_info diventano una risorsa citabile (lato finanziamento)."""
    pop_url = (
        "https://esploradati.istat.it/SDMXWS/rest/data/22_289/A.110002.JAN..9.99"
        "?startPeriod=2020"
    )
    oc_url = "https://opencoesione.gov.it/it/api/aggregati/territori/comune-di-x.json"
    welfare_info = {
        "comune": "110002", "anno": "2023", "popolazione": 27000,
        "indice_vecchiaia": 248.3, "indice_dipendenza_anziani": 41.2,
        "indice_dipendenza_strutturale": 58.0, "pct_over_65": 26.0, "pct_under_15": 10.5,
        "source_url": pop_url,
        "investimenti_sociali": {
            "finanziato_totale": 340000.0, "pagamenti_totali": 120000.0,
            "spend_ratio": 0.35, "progetti_totali": 4, "source_url": oc_url,
        },
    }
    ev_pop = {"fonte": "istat", "url": pop_url, "dettaglio": "indice vecchiaia 248,3"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[_idea("welfare", [ev_pop])],
        )
    )
    parts = [_participant("opencoesione", "Narrativa.", [
        {"name": "aggregati", "url": _OC_URL, "format": "JSON", "content": None},
    ])]
    aggregate = build_programma_aggregator(
        agent, _IDEE_REQ, welfare_info=welfare_info  # type: ignore[arg-type]
    )
    resp = (await aggregate(parts)).response
    assert resp is not None
    # display-clean: ISTAT → sito di origine; OpenCoesione aggregati → homepage.
    assert any(r.url == "https://www.istat.it/" for r in resp.citazioni)       # ancora ISTAT
    assert any(r.url == "https://opencoesione.gov.it/" for r in resp.citazioni)  # OpenCoesione


@pytest.mark.asyncio
async def test_scheda_mode_is_unaffected_by_generator_rules() -> None:
    """Regressione: la modalità scheda ignora i requisiti per generatore."""
    agent = _StubProgrammaAgent(_llm_json())  # proposta senza generatore
    aggregate = build_programma_aggregator(agent, _REQ)  # type: ignore[arg-type]
    resp = (await aggregate(_participants())).response
    assert resp is not None and len(resp.proposte) == 1


def test_idee_task_asks_for_generator_inputs() -> None:
    task = build_programma_task(_IDEE_REQ, None)
    assert "gap_by_tema" in task and "stalled_projects" in task
    assert "similar_projects" in task
    # La modalità scheda non chiede i kind comparativi.
    assert "gap_by_tema" not in build_programma_task(_REQ, None)


# ───────────────── modalità completa: report unico (feedback collaudo) ─────


@pytest.mark.asyncio
async def test_completa_merges_scheda_and_idee_from_one_fanout() -> None:
    """UN fan-out alimenta entrambi gli agenti: SWOT+sintesi dalla scheda,
    idee taggate col generatore fuse nello stesso report."""
    scheda_agent = _StubProgrammaAgent(
        _llm_json(sintesi="Quadro descrittivo del territorio con numeri chiave.")
    )
    idee_agent = _StubProgrammaAgent(
        _llm_json(
            sintesi="",
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[
                _idea("gap_comparativo", [
                    {"fonte": "opencoesione", "url": _PROJ_URL, "dettaglio": "x"}
                ]),
            ],
        )
    )
    req = ProgrammaRequest(cod_comune="110002", comune_nome="Barletta", modalita="completa")
    parts = _participants()
    parts[0] = _participant(
        "opencoesione", "Narrativa.",
        [{"name": "progetto peer", "url": _PROJ_URL, "format": "JSON", "content": None},
         {"name": "capacità", "url": _OC_URL, "format": "JSON", "content": None}],
    )
    aggregate = build_programma_aggregator(
        scheda_agent, req, idee_agent=idee_agent  # type: ignore[arg-type]
    )
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert resp.sintesi.startswith("Quadro descrittivo")
    assert len(resp.swot["forze"]) == 1  # dalla scheda
    senza_gen = [p for p in resp.proposte if not p.generatore]
    con_gen = [p for p in resp.proposte if p.generatore]
    assert len(senza_gen) == 1 and len(con_gen) == 1
    assert con_gen[0].generatore == "gap_comparativo"
    # Entrambi gli agenti hanno ricevuto lo STESSO bundle (un solo fan-out).
    assert scheda_agent.last_prompt == idee_agent.last_prompt


def test_completa_requires_idee_agent() -> None:
    req = ProgrammaRequest(cod_comune="110002", modalita="completa")
    with pytest.raises(ValueError, match="idee_agent"):
        build_programma_aggregator(_StubProgrammaAgent("{}"), req)  # type: ignore[arg-type]


# ───────────────── modalità marketing: spunti di attrattività (Pezzo 10) ────

_OSM_URL = "https://www.openstreetmap.org/way/12345"
_WEB_URL = "https://comune-altrove.gov.it/turismo-lento"
_MARKETING_REQ = ProgrammaRequest(
    cod_comune="110002", comune_nome="Barletta", modalita="marketing"
)


def _spunto(generatore: str | None, lente: str, evidenze: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "titolo": f"Spunto {generatore}",
        "descrizione": "d",
        "generatore": generatore,
        "lente": lente,
        "evidenze": evidenze,
        "finanziamento": None,
        "fattibilita": {"livello": "media", "motivazione": "m", "spend_ratio_storico": None},
    }


@pytest.mark.asyncio
async def test_marketing_mode_enforces_local_plus_external() -> None:
    """Regola (A)+(B): ogni spunto cita una premessa locale + un precedente web,
    e il `generatore` deve essere di marketing — altrimenti è SCARTATO."""
    ev_local = {"fonte": "osm", "url": _OSM_URL, "dettaglio": "POI castello"}
    ev_web = {"fonte": "web", "url": _WEB_URL, "dettaglio": "spunto da: comune X"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[
                _spunto("caso_analogo", "turismo_cultura", [ev_local, ev_web]),    # ok
                _spunto("asset_sottoutilizzato", "turismo_cultura", [ev_local]),   # manca web → out
                _spunto("domanda_emergente", "viabilita_mobilita", [ev_web]),      # manca locale → out
                _spunto("gap_comparativo", "turismo_cultura", [ev_local, ev_web]), # gen non marketing → out
            ],
        )
    )
    parts = [
        _participant(
            "osm", "Asset locali.",
            [{"name": "castello", "url": _OSM_URL, "format": "JSON", "content": None}],
        ),
        _participant(
            "web", "Iniziative di altri enti.",
            [{"name": "turismo lento", "url": _WEB_URL, "format": "WEB", "content": None}],
        ),
    ]
    aggregate = build_programma_aggregator(
        agent, _MARKETING_REQ, marketing_agent=agent  # type: ignore[arg-type]
    )
    resp = (await aggregate(parts)).response
    assert resp is not None
    assert [p.generatore for p in resp.proposte] == ["caso_analogo"]
    kept = resp.proposte[0]
    assert kept.lente == "turismo_cultura"
    # fonte_tipo derivato: la premessa locale e l'ispirazione esterna distinte.
    tipi = {e.fonte_tipo for e in kept.evidenze}
    assert tipi == {"dato_locale", "ispirazione_esterna"}


def test_marketing_requires_marketing_agent() -> None:
    req = ProgrammaRequest(cod_comune="110002", modalita="marketing")
    with pytest.raises(ValueError, match="marketing_agent"):
        build_programma_aggregator(_StubProgrammaAgent("{}"), req)  # type: ignore[arg-type]


def test_marketing_task_asks_for_external_initiatives() -> None:
    task = build_programma_task(_MARKETING_REQ, None)
    assert "MARKETING" in task.upper() and "site:gov.it" in task
    # Le altre modalità non chiedono la ricerca web di iniziative altrui.
    assert "MARKETING" not in build_programma_task(_REQ, None).upper()


def test_evidenza_fonte_tipo_is_derived_from_fonte() -> None:
    web = Evidenza(fonte="web", url=_WEB_URL, dettaglio="d")
    assert web.fonte_tipo == "ispirazione_esterna"
    loc = Evidenza(fonte="osm", url=_OSM_URL, dettaglio="d")
    assert loc.fonte_tipo == "dato_locale"
    # Derivato e NON falsificabile: l'LLM non può marcare il web come locale.
    forged = Evidenza(fonte="web", url=_WEB_URL, dettaglio="d", fonte_tipo="dato_locale")
    assert forged.fonte_tipo == "ispirazione_esterna"


def test_marketing_rejects_external_only_and_keeps_anchored() -> None:
    ext_only = Proposta(
        titolo="solo esterno", descrizione="d",
        generatore="caso_analogo", lente="turismo_cultura",
        evidenze=[Evidenza(fonte="web", url=_WEB_URL, dettaglio="x")],
        fattibilita=Fattibilita(livello="alta", motivazione="m"),
    )
    out = validate_programma(_resp([ext_only]), {_WEB_URL}, modalita="marketing")
    assert out.proposte == []  # senza premessa locale → scartato

    anchored = Proposta(
        titolo="ancorato", descrizione="d",
        generatore="caso_analogo", lente="turismo_cultura",
        evidenze=[
            Evidenza(fonte="osm", url=_OSM_URL, dettaglio="asset"),
            Evidenza(fonte="web", url=_WEB_URL, dettaglio="spunto da: comune X"),
        ],
        fattibilita=Fattibilita(livello="alta", motivazione="m"),
    )
    out2 = validate_programma(_resp([anchored]), {_OSM_URL, _WEB_URL}, modalita="marketing")
    assert len(out2.proposte) == 1
    # Marketing non è ancorato a un fondo: niente finanziamento NON degrada a
    # da_verificare (regola che vale solo per scheda/idee).
    assert out2.proposte[0].fattibilita.livello == "alta"


@pytest.mark.asyncio
async def test_project_rows_become_named_citations() -> None:
    """similar_projects: ogni progetto peer diventa citazione nominata —
    indispensabile perché le idee possano linkare cosa hanno fatto i simili."""
    from opendata_backend.orchestrator.synth import _project_citations_from_rows

    payload = {
        "kind": "similar_projects",
        "rows": {"progetti": [
            {"clp": "PEER1", "url": _PROJ_URL, "titolo": "Comunità energetica PIP",
             "comune": "Bisceglie", "finanziato": 1000.0},
            {"clp": "NOURL", "titolo": "senza url"},
        ]},
        "source_url": "https://opencoesione.gov.it/it/opendata/",
    }
    cits = _project_citations_from_rows(payload)
    assert len(cits) == 1
    assert cits[0].url == _PROJ_URL
    assert "Comunità energetica PIP" in cits[0].name and "Bisceglie" in cits[0].name


def test_sintesi_passes_guardrails_but_persuasion_is_stripped() -> None:
    resp = _resp([])
    resp.sintesi = "Il comune conta 92.798 residenti e 753 progetti di coesione."
    out = validate_programma(resp, set())
    assert out.sintesi.startswith("Il comune conta")

    resp2 = _resp([])
    resp2.sintesi = "Votate per noi: risultati straordinari garantiti!"
    out2 = validate_programma(resp2, set())
    assert out2.sintesi == ""


# ───────────────────── tier documentale (Pezzo 9) ──────────────────────────


def test_evidenza_tier_is_derived_from_fonte() -> None:
    kg = Evidenza(fonte="kg", url="kg://comune-110002/d1#p=3", dettaglio="d")
    assert kg.tier == "documentale"
    oc = Evidenza(fonte="opencoesione", url=_OC_URL, dettaglio="d")
    assert oc.tier == "certificato"
    # Il tier non è falsificabile dall'LLM: viene riderivato dal validator.
    forged = Evidenza(fonte="kg", url="kg://x/d", dettaglio="d", tier="certificato")
    assert forged.tier == "documentale"


def test_feasibility_never_high_on_documentary_evidence_alone() -> None:
    kg_url = "https://kg.example.org/documents/doc-123"
    prop = Proposta(
        titolo="Riuso area da PUG",
        descrizione="d",
        evidenze=[Evidenza(fonte="kg", url=kg_url, dettaglio="PUG p.12")],
        finanziamento=Finanziamento(linea="PR FESR", fonte_url=kg_url, stato="aperto"),
        fattibilita=Fattibilita(livello="alta", motivazione="m"),
    )
    out = validate_programma(_resp([prop]), {kg_url})
    assert out.proposte[0].fattibilita.livello == "media"  # mai alta su solo documentale

    # Con un riscontro certificato accanto, "alta" sopravvive.
    prop2 = Proposta(
        titolo="Riuso con riscontro",
        descrizione="d",
        evidenze=[
            Evidenza(fonte="kg", url=kg_url, dettaglio="PUG p.12"),
            Evidenza(fonte="opencoesione", url=_OC_URL, dettaglio="ratio 0.8"),
        ],
        finanziamento=Finanziamento(linea="PR FESR", fonte_url=_OC_URL, stato="aperto"),
        fattibilita=Fattibilita(livello="alta", motivazione="m"),
    )
    out2 = validate_programma(_resp([prop2]), {kg_url, _OC_URL})
    assert out2.proposte[0].fattibilita.livello == "alta"


def test_router_audit_summary_is_informative() -> None:
    from opendata_backend.orchestrator.parsing import Resource
    from opendata_backend.routers.programma import _summary

    resp = _resp([])
    resp.citazioni = [
        Resource(name="a", url="https://x/1", format="JSON", source="opencoesione"),
        Resource(name="b", url="https://x/2", format="CSV", source="istat"),
    ]
    s = _summary(resp)
    assert "110002" in s and "0 voci SWOT" in s and "2 citazioni" in s
    assert "istat" in s and "opencoesione" in s
