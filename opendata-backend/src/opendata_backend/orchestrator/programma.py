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

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

from agent_framework import Agent
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

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
    # Tag della fonte (istat, opencoesione, …). Tipato str e normalizzato, non
    # Literal: i modelli piccoli producono typo ("ospr") e una voce malformata
    # non deve invalidare la scheda — il guardrail vero è l'URL risolvibile.
    fonte: str
    url: str  # risolvibile, copiata VERBATIM dalle risorse raccolte
    dettaglio: str  # cosa dice il dato (no interpretazione)
    # Tier (spec 09): "certificato" = dato aperto ufficiale; "documentale" =
    # fatto da documenti comunali ingeriti nel KG (delibere, piani, bilanci).
    # DERIVATO dalla fonte, mai dall'LLM: kg → documentale, il resto certificato.
    tier: Literal["certificato", "documentale"] = "certificato"

    @field_validator("fonte")
    @classmethod
    def _normalise_fonte(cls, v: str) -> str:
        # i modelli piccoli copiano il tag con la decorazione ("[opencoesione]")
        return v.strip().strip("[]()").strip().lower()

    @model_validator(mode="after")
    def _derive_tier(self) -> "Evidenza":
        self.tier = "documentale" if self.fonte == "kg" else "certificato"
        return self


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
    # Modalità "idee" (Pezzo 8): da quale scarto nasce l'idea. Obbligatorio in
    # modalità idee (i guardrail scartano le proposte senza generatore valido);
    # assente in modalità scheda. str normalizzato, non Literal (lezione del
    # campo `fonte`: un typo non deve invalidare il parse — lo gestisce il
    # guardrail).
    generatore: str | None = None

    @field_validator("generatore")
    @classmethod
    def _normalise_generatore(cls, v: str | None) -> str | None:
        return v.strip().lower() if isinstance(v, str) and v.strip() else None


class ProgrammaRequest(BaseModel):
    cod_comune: str  # codice ISTAT, es. "072006"
    # Nome del comune: gli specialisti che geocodificano (OSM) o cercano per
    # testo (CKAN) non sanno risolvere il codice ISTAT — senza nome l'agente
    # OSM finisce a geocodificare "zona industriale, Italia" (visto in smoke).
    comune_nome: str | None = None
    zona: str | None = None  # descrizione testuale (fallback)
    zona_tipo: str | None = None  # tassonomia ZonaTipo (Pezzo 6); None = livello comune
    zona_osm_id: str | None = None  # entità OSM selezionata, es. "way/123" (Pezzo 6)
    tema: str | None = None
    cicli: list[str] | None = None
    # "scheda" = fotografia SWOT (Pezzo 4); "idee" = brainstorming a quattro
    # generatori (Pezzo 8); "completa" = UN solo fan-out che alimenta ENTRAMBI
    # gli agenti → report unico (sintesi + SWOT + proposte + idee).
    modalita: Literal["scheda", "idee", "completa"] = "scheda"


class ProgrammaResponse(BaseModel):
    comune: str
    zona: str | None = None
    # Quadro descrittivo di apertura (prosa, 8-12 frasi): il "racconto" del
    # territorio coi numeri del bundle — risponde al feedback "troppo
    # schematica" del primo collaudo. Vuota se l'LLM non la produce.
    sintesi: str = ""
    swot: dict[str, list[VoceSwot]]  # chiavi: forze/debolezze/opportunita/minacce
    proposte: list[Proposta]
    citazioni: list[Resource]  # tutte le fonti risolvibili raccolte dagli specialisti
    disclaimer: str
    generato_il: datetime


class _LlmProgramma(BaseModel):
    """Il sottoinsieme che l'LLM emette — il resto lo assembla l'aggregatore."""

    sintesi: str = ""
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
    label = f"{req.cod_comune} ({req.comune_nome})" if req.comune_nome else req.cod_comune
    parts = [
        f"Raccogli evidenze sul comune con codice ISTAT {label}"
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
    if req.modalita in ("idee", "completa"):
        parts.append(
            "MODALITÀ BRAINSTORMING: oltre a quanto sopra, raccogli anche — se i "
            "tuoi tool lo permettono — i temi dove comuni comparabili hanno "
            "finanziato e questo comune no (kind gap_by_tema), i progetti di "
            "comuni simili (kind similar_projects), i progetti locali fermi "
            "(kind stalled_projects), le risorse programmate e non ancora spese "
            "per tema (aggregati territoriali), gli indicatori critici e "
            "l'accessibilità della zona."
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
    """Estrae il JSON della scheda; tollera fence markdown e preamboli.

    La validazione è PER VOCE: un item malformato (typo nei campi, shape
    sbagliata) viene scartato col log, non invalida l'intera scheda — visto
    in smoke con un modello piccolo che ha emesso `fonte: "ospr"`.
    """
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
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("La risposta del programma_agent non è un oggetto JSON")

    out = _LlmProgramma(
        sintesi=str(data.get("sintesi") or ""),
        disclaimer=str(data.get("disclaimer") or ""),
    )
    swot_raw = data.get("swot") if isinstance(data.get("swot"), dict) else {}
    for key in SWOT_KEYS:
        items = swot_raw.get(key) if isinstance(swot_raw.get(key), list) else []
        kept: list[VoceSwot] = []
        for item in items:
            try:
                kept.append(VoceSwot.model_validate(item))
            except ValidationError:
                log.warning("voce SWOT '%s' malformata scartata: %.80s", key, item)
        out.swot[key] = kept
    proposte_raw = data.get("proposte") if isinstance(data.get("proposte"), list) else []
    for item in proposte_raw:
        try:
            out.proposte.append(Proposta.model_validate(item))
        except ValidationError:
            log.warning("proposta malformata scartata: %.80s", item)
    return out


# ─────────────────────────── aggregatore ────────────────────────────────────


def build_programma_aggregator(
    programma_agent: Agent,
    req: ProgrammaRequest,
    *,
    idee_agent: Agent | None = None,
    instructions_hint: str | None = None,
) -> Callable[[list[Any]], Awaitable[ProgrammaOutput]]:
    """Aggregatore per ConcurrentBuilder: evidenze → scheda validata.

    Con `modalita="completa"` il bundle di evidenze (la parte costosa: UN solo
    fan-out) alimenta ENTRAMBI gli agenti — `programma_agent` per sintesi+SWOT+
    proposte e `idee_agent` per le idee dei quattro generatori — e le proposte
    vengono fuse nello stesso report, ciascuna validata con le regole della
    propria modalità.

    `instructions_hint` è il gancio parametrico residuo: testo aggiuntivo
    anteposto alla richiesta, senza toccare l'impianto.
    """
    if req.modalita == "completa" and idee_agent is None:
        raise ValueError("modalita='completa' richiede anche idee_agent")

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
            # dedupe per URL mantenendo l'ordine — anche DENTRO lo stesso
            # partecipante (più chiamate allo stesso tool → stessa citazione).
            seen = {r.url.strip() for r in all_resources}
            unique: list[Resource] = []
            for r in resources:
                key = r.url.strip()
                if key in seen:
                    continue
                seen.add(key)
                unique.append(r)
            resources = unique
            all_resources.extend(resources)
            sections.append(_bundle_section(str(source), narrative, resources))

        evidence_urls = {r.url.strip() for r in all_resources}
        bundle = "\n\n".join(sections)
        prompt_parts = [_request_header(req)]
        if instructions_hint:
            prompt_parts.append(instructions_hint)
        prompt_parts.append("EVIDENZE RACCOLTE:\n\n" + bundle)
        prompt = "\n\n".join(prompt_parts)

        async def _run(agent: Agent, label: str) -> _LlmProgramma:
            try:
                llm_result = await agent.run(prompt)
                raw = (getattr(llm_result, "text", None) or str(llm_result)).strip()
                return _parse_llm_json(raw)
            except Exception:
                log.exception("%s agent failed; sezione vuota", label)
                return _LlmProgramma()

        def _build(parsed: _LlmProgramma, modalita: str) -> ProgrammaResponse:
            resp = ProgrammaResponse(
                comune=req.cod_comune,
                zona=req.zona,
                sintesi=parsed.sintesi,
                swot={k: parsed.swot.get(k, []) for k in SWOT_KEYS},
                proposte=parsed.proposte,
                citazioni=all_resources,
                disclaimer=parsed.disclaimer,
                generato_il=datetime.now(timezone.utc),
            )
            return validate_programma(resp, evidence_urls, modalita=modalita)

        if req.modalita == "completa":
            # Un solo fan-out (già pagato), due sintesi in parallelo: la
            # scheda (sintesi+SWOT+proposte) e le idee dei generatori — ogni
            # parte validata con le regole della propria modalità, poi fuse.
            parsed_scheda, parsed_idee = await asyncio.gather(
                _run(programma_agent, "programma"),
                _run(idee_agent, "idee"),  # type: ignore[arg-type]
            )
            response = _build(parsed_scheda, "scheda")
            response_idee = _build(parsed_idee, "idee")
            # Le idee si riconoscono dal `generatore`; niente duplicati per titolo.
            titoli = {p.titolo.strip().lower() for p in response.proposte}
            response.proposte += [
                p for p in response_idee.proposte
                if p.titolo.strip().lower() not in titoli
            ]
            if not response.disclaimer.strip() and response_idee.disclaimer.strip():
                response.disclaimer = response_idee.disclaimer
        else:
            agent = idee_agent if (req.modalita == "idee" and idee_agent) else programma_agent
            response = _build(await _run(agent, req.modalita), req.modalita)

        return ProgrammaOutput(
            text=response.model_dump_json(),
            response=response,
            evidence_sources=sorted({str(r.source) for r in all_resources if r.source}),
        )

    return aggregate
