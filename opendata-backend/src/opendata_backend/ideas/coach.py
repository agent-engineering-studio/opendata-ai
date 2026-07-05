"""Coach dell'Idea Lab — facilita il percorso di brainstorming a tappe.

Un solo turno LLM per messaggio utente via `llm.complete()` (provider-agnostico,
R11): il transcript viene serializzato nel prompt insieme all'evidenza
deterministica (dataset con qualità + progetti finanziati comparabili) e il
modello risponde in JSON `{reply, next_stage, suggestions}`. Quando il
provider non è configurato o fallisce, ogni tappa ha una risposta offline
deterministica costruita dai soli dati — il percorso non si interrompe mai.
"""

from __future__ import annotations

import json
import logging

from ..config import Settings
from ..llm import complete
from .discovery import discover_datasets, discover_funding
from .models import (
    AREAS,
    STAGE_LABELS,
    STAGES,
    ChatMessage,
    FundingProject,
    IdeaChatRequest,
    IdeaChatResponse,
    IdeaDataset,
)

log = logging.getLogger("opendata-backend.ideas")

_SYSTEM = (
    "Sei il facilitatore dell'Idea Lab di un portale open data italiano: guidi "
    "un ente pubblico o un cittadino, con un percorso di brainstorming a tappe, "
    "dalla materia prima (i dataset aperti) a un'idea progettuale concreta, "
    "candidabile a fondi pubblici. Regole: parla italiano, professionale ma "
    "colloquiale; UNA sola domanda per turno; fonda ogni affermazione sui "
    "dataset e sui progetti finanziati che ti vengono forniti, citandoli per "
    "titolo; se un dato necessario non esiste tra i dataset forniti, dillo "
    "esplicitamente e trattalo come 'gap di dati' da colmare, non inventarlo."
)

_STAGE_GOALS: dict[str, str] = {
    "inquadramento": (
        "Obiettivo della tappa: capire la sfida. Fai emergere: qual è il "
        "problema concreto, chi sono i beneficiari, cosa vorrebbe ottenere "
        "l'ente. Quando il quadro è chiaro passa a 'esplorazione'."
    ),
    "esplorazione": (
        "Obiettivo della tappa: leggere insieme l'evidenza. Presenta i dataset "
        "trovati (titolo, qualità in stelle, aggiornamento), evidenzia i più "
        "solidi e i punti deboli (licenze, freschezza), e segnala quali dati "
        "utili MANCANO (gap). Quando l'utente ha chiaro su cosa può costruire "
        "passa a 'divergenza'."
    ),
    "divergenza": (
        "Obiettivo della tappa: generare 3-4 idee alternative ancorate ai "
        "dataset disponibili, ciascuna con titolo, una riga di descrizione e i "
        "dataset che userebbe. Idee diverse tra loro (servizio al cittadino, "
        "strumento per l'ente, analisi/monitoraggio...). Poi chiedi quale "
        "approfondire e passa a 'convergenza'."
    ),
    "convergenza": (
        "Obiettivo della tappa: stress-test dell'idea scelta. Sii critico: "
        "esiste già? i dati la reggono davvero? chi la manterrebbe? Poi "
        "valuta la finanziabilità usando i progetti comparabili già "
        "finanziati che ti sono stati forniti. Quando l'idea regge, passa a "
        "'sintesi'."
    ),
    "sintesi": (
        "Obiettivo della tappa: chiudere il percorso. Riassumi l'idea finale "
        "in 3-4 righe e invita l'utente a generare la scheda progetto "
        "completa (bottone 'Genera la scheda'). next_stage resta 'sintesi'."
    ),
}


def resolve_stage(requested: str | None, n_user_messages: int) -> str:
    if requested in STAGES:
        return requested  # type: ignore[return-value]
    # Prima richiesta senza stage: si parte dall'inquadramento; se l'utente ha
    # già scritto più volte (client vecchio o retry) si avanza in proporzione.
    return STAGES[min(max(n_user_messages - 1, 0), 1)]


def _next_stage(current: str) -> str:
    i = STAGES.index(current)
    return STAGES[min(i + 1, len(STAGES) - 1)]


def _clamp_stage(current: str, proposed: str | None) -> str:
    """Il coach può restare o avanzare di una tappa, mai saltare o tornare indietro."""
    if proposed not in STAGES:
        return current
    cur_i, prop_i = STAGES.index(current), STAGES.index(proposed)
    return STAGES[min(max(prop_i, cur_i), cur_i + 1)]


def _transcript(messages: list[ChatMessage], *, max_chars: int = 6000) -> str:
    lines = [
        ("Utente: " if m.role == "user" else "Facilitatore: ") + m.content.strip()
        for m in messages
    ]
    text = "\n".join(lines)
    return text[-max_chars:]


def _datasets_block(datasets: list[IdeaDataset]) -> str:
    if not datasets:
        return "(nessun dataset trovato finora)"
    return "\n".join(
        f"- {d.title} — {d.quality_note}; formati: {', '.join(d.formats) or 'n/d'}; {d.url}"
        for d in datasets
    )


def _funding_block(funding: list[FundingProject]) -> str:
    if not funding:
        return "(nessun progetto comparabile recuperato)"
    lines = []
    for p in funding:
        amount = (
            f"{p.finanziamento_totale:,.0f} €".replace(",", ".")
            if p.finanziamento_totale
            else "importo n/d"
        )
        lines.append(f"- {p.titolo} — {amount}, ciclo {p.ciclo or 'n/d'}, stato {p.stato or 'n/d'}")
    return "\n".join(lines)


def _challenge_text(messages: list[ChatMessage]) -> str:
    return " ".join(m.content for m in messages if m.role == "user")


def parse_coach_json(raw: str) -> dict | None:
    """JSON del coach, tollerante a code-fence e troncature (json_repair)."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except Exception:
        try:
            from json_repair import repair_json

            data = json.loads(repair_json(text))
        except Exception:
            return None
    return data if isinstance(data, dict) else None


# ─────────────────────────── fallback offline ───────────────────────────


def _offline_reply(
    stage: str,
    *,
    area: str | None,
    datasets: list[IdeaDataset],
    funding: list[FundingProject],
) -> tuple[str, list[str]]:
    label = AREAS[area]["label"].lower() if area else "scelta"
    if stage == "inquadramento":
        return (
            f"Partiamo dalla sfida nell'area {label}: qual è il problema concreto "
            "che vorresti affrontare, e chi ne beneficerebbe?",
            ["Un servizio per i cittadini", "Uno strumento per l'ente", "Non lo so ancora"],
        )
    if stage == "esplorazione":
        top = datasets[:5]
        if top:
            elenco = "\n".join(f"- **{d.title}** ({d.quality_note})" for d in top)
            deboli = [d.title for d in top if d.stars <= 2 or not d.license_open]
            nota = (
                f"\n\nAttenzione a: {', '.join(deboli)} — qualità o licenza da verificare."
                if deboli
                else ""
            )
            reply = f"Ecco i dataset più pertinenti trovati sul portale:\n{elenco}{nota}"
        else:
            reply = (
                "Non ho trovato dataset pertinenti sul portale: è già un'informazione "
                "importante — il primo gap di dati da segnalare all'ente."
            )
        return reply, ["Quali dati mancano?", "Passiamo alle idee"]
    if stage == "divergenza":
        nomi = [d.title for d in datasets[:3]]
        base = nomi[0] if nomi else "i dati disponibili"
        return (
            "Alcune direzioni possibili:\n"
            f"1. **Servizio informativo al cittadino** costruito su {base}\n"
            "2. **Cruscotto di monitoraggio per l'ente** con indicatori aggiornati\n"
            "3. **Analisi dei divari territoriali** per orientare gli interventi\n"
            "Quale vuoi approfondire?",
            ["La 1", "La 2", "La 3"],
        )
    if stage == "convergenza":
        fin = (
            f"In regione risultano {len(funding)} progetti comparabili già finanziati: "
            "un segnale che questa linea è candidabile a fondi pubblici."
            if funding
            else "Non ho recuperato progetti comparabili: la finanziabilità va verificata sul sito OpenCoesione."
        )
        return (
            "Mettiamo l'idea alla prova: esiste già qualcosa di simile? I dataset "
            f"reggono l'uso previsto? Chi la manterrebbe dopo il lancio? {fin}",
            ["L'idea regge, chiudiamo", "Cambiamo idea"],
        )
    return (
        "Il percorso è completo: genera la scheda progetto per avere l'analisi "
        "completa — evidenza dai dati, finanziabilità, gap da colmare e kit di "
        "implementazione per il team di sviluppo.",
        ["Genera la scheda"],
    )


# ─────────────────────────── turno di chat ───────────────────────────


async def run_chat_turn(settings: Settings, req: IdeaChatRequest) -> IdeaChatResponse:
    n_user = sum(1 for m in req.messages if m.role == "user")
    stage = resolve_stage(req.stage, n_user)
    challenge = _challenge_text(req.messages)

    # Evidenza deterministica: si scopre una volta sola (poi il client la rimanda).
    datasets = list(req.datasets or [])
    funding = list(req.funding or [])
    needs_evidence = stage != "inquadramento" or n_user >= 2
    if not datasets and needs_evidence and challenge:
        datasets = await discover_datasets(
            settings, area=req.area, challenge_text=challenge, base_url=req.base_url
        )
    if not funding and needs_evidence and req.area:
        funding = await discover_funding(settings, area=req.area)

    prompt = (
        f"TAPPA CORRENTE: {stage} — {_STAGE_GOALS[stage]}\n\n"
        f"AREA: {AREAS[req.area]['label'] if req.area else 'non indicata'}"
        f" | TERRITORIO: {req.territory or 'non indicato'}\n\n"
        f"DATASET DISPONIBILI (con qualità):\n{_datasets_block(datasets)}\n\n"
        f"PROGETTI COMPARABILI GIÀ FINANZIATI (OpenCoesione):\n{_funding_block(funding)}\n\n"
        f"CONVERSAZIONE FINORA:\n{_transcript(req.messages)}\n\n"
        "Rispondi SOLO con un oggetto JSON: {\"reply\": \"<risposta al prossimo "
        "turno, markdown consentito>\", \"next_stage\": \"<una tra "
        + ", ".join(STAGES)
        + ">\", \"suggestions\": [\"<max 3 risposte rapide>\"]}"
    )
    raw = await complete(
        settings, prompt=prompt, system=_SYSTEM, max_tokens=900, temperature=0.3
    )

    if raw is not None and (data := parse_coach_json(raw)) and data.get("reply"):
        new_stage = _clamp_stage(stage, str(data.get("next_stage") or ""))
        suggestions = [str(s) for s in (data.get("suggestions") or [])][:3]
        reply = str(data["reply"])
        offline = False
    else:
        if raw is not None:
            log.warning("ideas coach: risposta LLM non parsabile, uso il fallback")
        # Offline si avanza PRIMA e si risponde per la tappa nuova: l'utente ha
        # appena risposto alla domanda della tappa precedente.
        new_stage = _next_stage(stage) if stage != "inquadramento" or n_user >= 2 else stage
        reply, suggestions = _offline_reply(
            new_stage, area=req.area, datasets=datasets, funding=funding
        )
        offline = raw is None

    return IdeaChatResponse(
        reply=reply,
        stage=new_stage,
        stage_label=STAGE_LABELS[new_stage],
        datasets=datasets,
        funding=funding,
        suggestions=suggestions,
        report_ready=new_stage == "sintesi",
        offline=offline,
    )
