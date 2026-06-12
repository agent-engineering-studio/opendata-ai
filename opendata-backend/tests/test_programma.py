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
    assert {r.url for r in resp.citazioni} == {_OC_URL, _ISTAT_URL}
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
    assert [r.url for r in resp.citazioni].count(_OC_URL) == 1


# ───────────────────────── modalità idee (Pezzo 8) ─────────────────────────

_AGG_URL = "https://opencoesione.gov.it/it/api/aggregati/territori/barletta-comune.json"
_SEARCH_URL = (
    "https://opencoesione.gov.it/it/api/progetti.json?territorio=barletta-comune"
)
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
    # NB: _OC_URL è esso stesso un URL "aggregati" → per i casi che devono
    # fallire il check finestra serve un URL OpenCoesione di RICERCA.
    ev_oc = {"fonte": "opencoesione", "url": _SEARCH_URL, "dettaglio": "x"}
    ev_agg = {"fonte": "opencoesione", "url": _AGG_URL, "dettaglio": "x"}
    ev_istat = {"fonte": "istat", "url": _ISTAT_URL, "dettaglio": "x"}
    agent = _StubProgrammaAgent(
        _llm_json(
            swot={"forze": [], "debolezze": [], "opportunita": [], "minacce": []},
            proposte=[
                _idea("gap_comparativo", [ev_oc]),              # ok
                _idea("fabbisogno", [ev_istat, ev_oc]),          # ok (indicatore + locale)
                _idea("fabbisogno", [ev_istat]),                 # manca la ricerca locale → out
                _idea("incompiuto", [ev_oc]),                    # ok
                _idea("finestra_finanziamento", [ev_agg]),       # ok (aggregati)
                _idea("finestra_finanziamento", [ev_oc]),        # non è un URL aggregati → out
                _idea(None, [ev_oc]),                            # senza generatore → out
                _idea("GAP_COMPARATIVO ", [ev_oc]),              # normalizzato → ok
            ],
        )
    )
    # Il bundle deve contenere anche l'URL aggregati perché superi il check URL.
    parts = _participants()
    parts[0] = _participant(
        "opencoesione",
        "Narrativa.",
        [
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
