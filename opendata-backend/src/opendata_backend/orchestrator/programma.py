"""Aggregatore "Programma Evidence-Based" — scheda SWOT + proposte per la PA.

Riusa il fan-out esistente con un aggregatore dedicato (stesso meccanismo di
`synth.build_aggregator`, contratto di output diverso): i partecipanti
raccolgono evidenze sul comune, un agente tool-less (`programma_agent`) le
trasforma nel JSON strutturato della scheda, e i guardrail deterministici di
`guardrails.validate_programma` scartano ogni claim senza fonte risolvibile.

Principio non negoziabile (spec 04): dato → evidenza → proposta. L'output è
analisi verificabile, non propaganda.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

from agent_framework import Agent
from pydantic import BaseModel, Field

from .guardrails import validate_programma
from .parsing import Resource, parse_agent_reply
from .synth import (
    _capture_tool_resources,
    _executor_id,
    _extract_text_from_result,
    _is_placeholder_url,
    _normalise_source_tag,
)

log = logging.getLogger("orchestrator.programma")

FonteEvidenza = Literal["istat", "opencoesione", "ckan", "eurostat", "oecd", "osm", "ispra"]

SWOT_KEYS = ("forze", "debolezze", "opportunita", "minacce")


# ─────────────────────────── contratto dati (spec 04 §6) ───────────────────


class Evidenza(BaseModel):
    fonte: FonteEvidenza
    url: str  # risolvibile, copiata VERBATIM dalle risorse raccolte
    dettaglio: str  # cosa dice il dato (no interpretazione)


class VoceSwot(BaseModel):
    testo: str
    evidenze: list[Evidenza]  # ≥1 obbligatoria (i guardrail scartano le orfane)


class Fattibilita(BaseModel):
    livello: Literal["alta", "media", "bassa", "da_verificare"]
    motivazione: str
    spend_ratio_storico: float | None = None  # da OpenCoesione


class Finanziamento(BaseModel):
    linea: str
    fonte_url: str
    stato: str | None = None


class Proposta(BaseModel):
    titolo: str
    descrizione: str
    evidenze: list[Evidenza]  # ≥1 obbligatoria
    finanziamento: Finanziamento | None = None
    fattibilita: Fattibilita


class ProgrammaRequest(BaseModel):
    cod_comune: str  # codice ISTAT, es. "072006"
    zona: str | None = None  # descrizione testuale (fallback)
    zona_tipo: str | None = None  # tassonomia ZonaTipo (Pezzo 6); None = livello comune
    zona_osm_id: str | None = None  # entità OSM selezionata, es. "way/123" (Pezzo 6)
    tema: str | None = None
    cicli: list[str] | None = None


class ProgrammaResponse(BaseModel):
    comune: str
    zona: str | None = None
    swot: dict[str, list[VoceSwot]]  # chiavi: forze/debolezze/opportunita/minacce
    proposte: list[Proposta]
    citazioni: list[Resource]  # tutte le fonti risolvibili raccolte dagli specialisti
    disclaimer: str
    generato_il: datetime


class _LlmProgramma(BaseModel):
    """Il sottoinsieme che l'LLM emette — il resto lo assembla l'aggregatore."""

    swot: dict[str, list[VoceSwot]] = Field(default_factory=dict)
    proposte: list[Proposta] = Field(default_factory=list)
    disclaimer: str = ""


@dataclass
class ProgrammaOutput:
    """Output-wrapper compatibile con `events.get_outputs()` (legge `.text`)."""

    text: str
    response: ProgrammaResponse | None = None
    evidence_sources: list[str] = field(default_factory=list)


# ─────────────────────────── evidence bundle ────────────────────────────────


def build_programma_task(
    req: ProgrammaRequest, zona_info: dict[str, Any] | None = None
) -> str:
    """Il task inviato ai partecipanti del fan-out (stessa query per tutti).

    `zona_info` è la zona OSM risolta dal Pezzo 6 ({name, centroid, bbox}):
    nome/centroide/bbox vengono iniettati nel task così gli specialisti geo
    (OSM per le distanze, ISPRA per i layer WFS) non rifanno il lookup.
    """
    parts = [
        f"Raccogli evidenze sul comune con codice ISTAT {req.cod_comune}"
    ]
    if zona_info:
        name = zona_info.get("name") or req.zona or "zona selezionata"
        parts.append(f"con particolare attenzione alla zona OSM: {name}")
        centroid = zona_info.get("centroid") or {}
        if centroid:
            parts.append(
                f"(centroide lat={centroid.get('lat'):.5f} lon={centroid.get('lon'):.5f}"
            )
            bbox = zona_info.get("bbox")
            if bbox:
                parts.append(
                    f", bbox sud={bbox[0]:.5f} ovest={bbox[1]:.5f} "
                    f"nord={bbox[2]:.5f} est={bbox[3]:.5f}"
                )
            parts.append(")")
    elif req.zona:
        parts.append(f"con particolare attenzione alla zona: {req.zona}")
    if req.zona_tipo:
        parts.append(f"(tipo di zona: {req.zona_tipo})")
    if req.tema:
        parts.append(f"sul tema: {req.tema}")
    if req.cicli:
        parts.append(f"per i cicli di programmazione: {', '.join(req.cicli)}")
    parts.append(
        "— servono: indicatori socioeconomici, progetti pubblici finanziati, "
        "capacità di spesa storica e dataset rilevanti."
    )
    return " ".join(parts)


def _bundle_section(source: str, narrative: str, resources: list[Resource]) -> str:
    lines = [f"=== {source.upper()} ===", narrative.strip() or "(nessun risultato)"]
    if resources:
        lines.append("RISORSE CITABILI (usa questi URL verbatim nelle `evidenze`):")
        for r in resources:
            lines.append(f"- [{r.source or source}] {r.name} | {r.url}")
    return "\n".join(lines)


def _request_header(req: ProgrammaRequest) -> str:
    rows = [f"comune ISTAT: {req.cod_comune}"]
    if req.zona:
        rows.append(f"zona: {req.zona}" + (f" (tipo: {req.zona_tipo})" if req.zona_tipo else ""))
    if req.tema:
        rows.append(f"tema: {req.tema}")
    if req.cicli:
        rows.append(f"cicli: {', '.join(req.cicli)}")
    return "RICHIESTA:\n" + "\n".join(rows)


def _parse_llm_json(raw: str) -> _LlmProgramma:
    """Estrae e valida il JSON della scheda; tollera fence markdown e preamboli."""
    text = raw.strip()
    if "```" in text:
        # taglia al primo blocco fenced (```json ... ```)
        chunks = text.split("```")
        for chunk in chunks[1:]:
            candidate = chunk.removeprefix("json").strip()
            if candidate.startswith("{"):
                text = candidate
                break
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"Nessun oggetto JSON nella risposta del programma_agent: {raw[:200]}")
    return _LlmProgramma.model_validate(json.loads(text[start : end + 1]))


# ─────────────────────────── aggregatore ────────────────────────────────────


def build_programma_aggregator(
    programma_agent: Agent,
    req: ProgrammaRequest,
    *,
    instructions_hint: str | None = None,
) -> Callable[[list[Any]], Awaitable[ProgrammaOutput]]:
    """Aggregatore per ConcurrentBuilder: evidenze → scheda validata.

    `instructions_hint` è il gancio parametrico per il Pezzo 8 (modalità
    "idee"): testo aggiuntivo anteposto alla richiesta, senza toccare
    l'impianto. Per la modalità scheda resta None.
    """

    async def aggregate(results: list[Any]) -> ProgrammaOutput:
        log.info("programma aggregator: %d participant results", len(results))
        sections: list[str] = []
        all_resources: list[Resource] = []

        for result in results:
            exec_id = _executor_id(result)
            tag = _normalise_source_tag(exec_id)
            source = tag or exec_id
            raw_text = _extract_text_from_result(result)
            narrative, resources = ("", [])
            if raw_text:
                narrative, resources = parse_agent_reply(raw_text)
            resources = [r for r in resources if not _is_placeholder_url(r.url)]
            resources = resources + _capture_tool_resources(result, tag)
            if tag:
                resources = [
                    r if r.source else r.model_copy(update={"source": tag})
                    for r in resources
                ]
            # dedupe per URL mantenendo l'ordine
            seen = {r.url.strip() for r in all_resources}
            resources = [r for r in resources if r.url.strip() not in seen]
            all_resources.extend(resources)
            sections.append(_bundle_section(str(source), narrative, resources))

        evidence_urls = {r.url.strip() for r in all_resources}
        bundle = "\n\n".join(sections)
        prompt_parts = [_request_header(req)]
        if instructions_hint:
            prompt_parts.append(instructions_hint)
        prompt_parts.append("EVIDENZE RACCOLTE:\n\n" + bundle)
        prompt = "\n\n".join(prompt_parts)

        llm_raw = ""
        try:
            llm_result = await programma_agent.run(prompt)
            llm_raw = (getattr(llm_result, "text", None) or str(llm_result)).strip()
            parsed = _parse_llm_json(llm_raw)
        except Exception:
            log.exception("programma_agent failed; returning empty scheda")
            parsed = _LlmProgramma()

        response = ProgrammaResponse(
            comune=req.cod_comune,
            zona=req.zona,
            swot={k: parsed.swot.get(k, []) for k in SWOT_KEYS},
            proposte=parsed.proposte,
            citazioni=all_resources,
            disclaimer=parsed.disclaimer,
            generato_il=datetime.now(timezone.utc),
        )
        response = validate_programma(response, evidence_urls)
        return ProgrammaOutput(
            text=response.model_dump_json(),
            response=response,
            evidence_sources=sorted({str(r.source) for r in all_resources if r.source}),
        )

    return aggregate
