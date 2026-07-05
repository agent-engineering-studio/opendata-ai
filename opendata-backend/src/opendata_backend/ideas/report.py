"""Scheda progetto finale dell'Idea Lab — il deliverable della tappa "sintesi".

Un solo passaggio LLM (via `llm.complete()`) distilla il percorso di
brainstorming in campi strutturati; tutto il packaging markdown è
deterministico, così le sezioni contrattuali ci sono SEMPRE, anche offline:

- evidenza dai dati (tabella dataset con qualità e citazioni);
- finanziabilità (progetti comparabili OpenCoesione + importi);
- gap di dati con piano per colmarli (la "domanda di riuso" verso l'ente);
- kit di implementazione: brief tecnico autosufficiente per il team di
  sviluppo, pronto da incollare in qualunque assistente AI di coding.
"""

from __future__ import annotations

import hashlib
import logging
import unicodedata
from datetime import UTC, datetime

from ..config import Settings
from ..llm import complete
from .coach import _challenge_text, _transcript, parse_coach_json
from .discovery import discover_datasets, discover_funding
from .models import (
    AREAS,
    FundingProject,
    IdeaDataset,
    IdeaReportRequest,
    IdeaReportResponse,
)

log = logging.getLogger("opendata-backend.ideas")


def stable_idea_id(titolo: str) -> str:
    """Content-hash deterministico (stesso schema degli item del programma)."""
    norm = unicodedata.normalize("NFKD", titolo).encode("ascii", "ignore").decode()
    digest = hashlib.sha1(" ".join(norm.lower().split()).encode()).hexdigest()[:12]
    return f"idea_{digest}"


_EXTRACT_SYSTEM = (
    "Distilli un percorso di brainstorming su open data in una scheda progetto "
    "per un ente pubblico italiano. Fondati SOLO sulla conversazione e "
    "sull'evidenza fornita; ciò che manca è un gap di dati, non un'invenzione."
)


def _extract_prompt(req: IdeaReportRequest, datasets: list[IdeaDataset]) -> str:
    from .coach import _datasets_block, _funding_block

    return (
        f"AREA: {AREAS[req.area]['label'] if req.area else 'non indicata'} | "
        f"TERRITORIO: {req.territory or 'non indicato'} | "
        f"IDEA SCELTA: {req.idea_titolo or 'da desumere dalla conversazione'}\n\n"
        f"DATASET DISPONIBILI:\n{_datasets_block(datasets)}\n\n"
        f"PROGETTI COMPARABILI FINANZIATI:\n{_funding_block(req.funding or [])}\n\n"
        f"CONVERSAZIONE:\n{_transcript(req.messages, max_chars=8000)}\n\n"
        'Rispondi SOLO con JSON: {"titolo": str, "problema": str, "soluzione": str, '
        '"beneficiari": str, "kpi": [str, max 4], '
        '"dataset_titoli": [titoli ESATTI dei dataset usati], '
        '"gap_dati": [{"dato": str, "perche_serve": str, "come_colmarlo": str, '
        '"caratteristiche": "<come deve essere il dato: granularità (es. per '
        "reparto/comune), frequenza di aggiornamento, formato machine-readable, "
        'licenza>"}], '
        '"passi": [str, max 5 passi di implementazione]}'
    )


def _offline_fields(req: IdeaReportRequest, datasets: list[IdeaDataset]) -> dict:
    label = AREAS[req.area]["label"].lower() if req.area else "open data"
    challenge = _challenge_text(req.messages)[:300]
    top = [d.title for d in datasets[:3]]
    return {
        "titolo": req.idea_titolo or f"Servizio informativo {label} basato su open data",
        "problema": challenge or f"Valorizzare i dati aperti dell'area {label}.",
        "soluzione": (
            "Un servizio digitale che integra i dataset pubblici disponibili in "
            "indicatori aggiornati e consultabili, per cittadini ed ente."
        ),
        "beneficiari": "Cittadini del territorio e uffici dell'ente.",
        "kpi": [
            "Numero di consultazioni mensili del servizio",
            "Numero di dataset sorgente integrati e aggiornati",
        ],
        "dataset_titoli": top,
        "gap_dati": [],
        "passi": [],
    }


# ─────────────────────────── sezioni markdown ───────────────────────────


def _fmt_eur(v: float | None) -> str:
    return f"{v:,.0f} €".replace(",", ".") if v else "n/d"


def _sezione_evidenza(datasets: list[IdeaDataset], usati: list[str]) -> str:
    if not datasets:
        return (
            "Nessun dataset pertinente è stato trovato sul portale: il progetto "
            "parte da un gap di dati (vedi sezione dedicata).\n"
        )
    rows = ["| Dataset | Qualità | Formati | Aggiornamento |", "|---|---|---|---|"]
    for d in datasets:
        marker = "**" if d.title in usati else ""
        rows.append(
            f"| {marker}[{d.title}]({d.url}){marker} | {d.stars}/5"
            f"{' · licenza aperta' if d.license_open else ' · licenza da verificare'}"
            f" | {', '.join(d.formats) or 'n/d'} | {d.modified or 'n/d'} |"
        )
    return (
        "\n".join(rows)
        + "\n\nIn **grassetto** i dataset su cui l'idea si fonda. La qualità è "
        "calcolata automaticamente dai metadati del portale (modello 5 stelle).\n"
    )


def _sezione_finanziabilita(funding: list[FundingProject], area: str | None) -> str:
    tema = AREAS[area]["oc_tema"] if area else None
    if not funding:
        return (
            "Non sono stati recuperati progetti comparabili da OpenCoesione: la "
            "finanziabilità va verificata manualmente su "
            "[opencoesione.gov.it](https://opencoesione.gov.it/it/)"
            + (f" (tema *{tema}*).\n" if tema else ".\n")
        )
    totale = sum(p.finanziamento_totale or 0 for p in funding)
    lines = [
        f"In regione risultano progetti comparabili già finanziati con fondi di "
        f"coesione{f' sul tema *{tema}*' if tema else ''} — un precedente concreto "
        f"per candidare questa idea (campione: {len(funding)} progetti, "
        f"{_fmt_eur(totale)} complessivi):",
        "",
    ]
    for p in funding[:5]:
        lines.append(
            f"- **{p.titolo}** — {_fmt_eur(p.finanziamento_totale)}, "
            f"ciclo {p.ciclo or 'n/d'}, stato {p.stato or 'n/d'}"
        )
    lines.append(
        "\nCanali da presidiare: programmi regionali/nazionali di coesione "
        "(FESR/FSE+), bandi regionali per l'innovazione digitale, fondi PNRR "
        "residui. Fonte progetti: [OpenCoesione](https://opencoesione.gov.it/it/).\n"
    )
    return "\n".join(lines)


def _sezione_gap(datasets: list[IdeaDataset], gap_dati: list[dict]) -> str:
    voci: list[str] = []
    for g in gap_dati:
        dato = str(g.get("dato") or "").strip()
        if not dato:
            continue
        riga = (
            f"- **{dato}** — {str(g.get('perche_serve') or 'necessario al progetto').strip()} "
            f"→ *{str(g.get('come_colmarlo') or 'pubblicare il dato sul portale regionale').strip()}*"
        )
        caratteristiche = str(g.get("caratteristiche") or "").strip()
        if caratteristiche:
            riga += f"\n  - Come deve essere: {caratteristiche}"
        voci.append(riga)
    deboli = [d for d in datasets if d.stars <= 2 or not d.license_open]
    for d in deboli:
        azioni = []
        if not d.license_open:
            azioni.append("esplicitare una licenza aperta (es. CC-BY 4.0)")
        if d.stars <= 2:
            azioni.append("pubblicare in formato aperto machine-readable (CSV/JSON)")
        if d.freshness_days and d.freshness_days > 365:
            azioni.append("ripristinare l'aggiornamento periodico")
        voci.append(f"- **Migliorare “{d.title}”** ({d.quality_note}) → *{'; '.join(azioni)}*")
    if not voci:
        voci.append("- Nessun gap bloccante individuato: la base dati regge il progetto.")
    intro = (
        "Il progetto vale anche come **domanda di riuso**: ogni gap qui sotto è "
        "una richiesta motivata all'ente per migliorare la base di dati aperti."
    )
    return intro + "\n\n" + "\n".join(voci) + "\n"


def _kit_implementazione(
    fields: dict,
    datasets: list[IdeaDataset],
    usati: list[str],
    *,
    area: str | None,
    territory: str | None,
) -> str:
    """Brief tecnico autosufficiente, dentro un blocco copiabile."""
    fonti = [d for d in datasets if d.title in usati] or datasets[:3]
    fonti_md = "\n".join(
        f"- {d.title}: {d.url} (formati: {', '.join(d.formats) or 'n/d'}; "
        f"qualità {d.stars}/5{'' if d.license_open else '; licenza da verificare prima del riuso'})"
        for d in fonti
    ) or "- (nessuna fonte individuata: partire dal portale regionale open data)"
    passi = fields.get("passi") or []
    milestone = [
        "Scaricare e profilare i dataset sorgente (righe, colonne, qualità, chiavi di join)",
        "Prototipo end-to-end su UN solo indicatore, dalla fonte alla visualizzazione",
        *[str(p) for p in passi[:5]],
        "Test con utenti reali e pubblicazione",
    ]
    milestone_md = "\n".join(f"{i}. {m}" for i, m in enumerate(milestone, 1))
    kpi_md = "\n".join(f"- {k}" for k in fields.get("kpi") or []) or "- Da definire con l'ente"
    brief = f"""# Brief di implementazione — {fields['titolo']}

## Contesto e obiettivo
{fields['problema']}
Soluzione attesa: {fields['soluzione']}
Beneficiari: {fields['beneficiari']}
Ambito: area {AREAS[area]['label'] if area else 'n/d'}, territorio {territory or 'Puglia'}.

## Fonti dati (aprire e ispezionare PRIMA di scrivere codice)
{fonti_md}

## Architettura suggerita (adattare alle competenze del team)
- Ingestion: job schedulato che scarica le fonti sopra, le valida e le normalizza in un database
- Backend: servizio REST che espone gli indicatori derivati, con data di estrazione per ogni valore
- Frontend: applicazione web responsive (dashboard/mappa) consultabile senza autenticazione

## Milestone
{milestone_md}

## Criteri di accettazione
- Ogni numero mostrato è tracciabile alla fonte: URL del dataset + data di estrazione visibili
- Il sistema segnala quando un dataset sorgente non risulta più aggiornato
{kpi_md}

## Vincoli e note
- Rispettare le licenze dei dataset e citare sempre la fonte
- I dati pubblici possono essere disallineati rispetto alla realtà: esporre la data di aggiornamento
- Nessun dato personale: usare solo dati aggregati/aperti"""
    return (
        "Il brief qui sotto è autosufficiente: contiene contesto, fonti, "
        "architettura e criteri di accettazione. Copialo e consegnalo al team "
        "di sviluppo — o incollalo nel tuo assistente AI di programmazione per "
        "partire subito dal prototipo.\n\n```text\n" + brief + "\n```\n"
    )


# ─────────────────────────── build ───────────────────────────


async def build_report(settings: Settings, req: IdeaReportRequest) -> IdeaReportResponse:
    challenge = _challenge_text(req.messages)
    datasets = list(req.datasets or [])
    funding = list(req.funding or [])
    if not datasets and challenge:
        datasets = await discover_datasets(settings, area=req.area, challenge_text=challenge)
    if not funding and req.area:
        funding = await discover_funding(settings, area=req.area)

    raw = await complete(
        settings,
        prompt=_extract_prompt(req, datasets),
        system=_EXTRACT_SYSTEM,
        max_tokens=1600,
        temperature=0.2,
    )
    parsed = parse_coach_json(raw) if raw is not None else None
    offline = parsed is None or not str(parsed.get("titolo") or "").strip()
    # I default offline sono SEMPRE la base: un JSON LLM parziale (titolo ok ma
    # senza problema/beneficiari) integra i campi che ha, senza mai KeyError.
    fields = _offline_fields(req, datasets)
    if not offline:
        fields.update({k: v for k, v in parsed.items() if v})
    elif raw is not None:
        log.warning("ideas report: estrazione LLM non parsabile, uso il fallback")

    titolo = str(fields["titolo"]).strip()
    idea_id = stable_idea_id(titolo)
    usati = [str(t) for t in fields.get("dataset_titoli") or []]
    gap_dati = [g for g in fields.get("gap_dati") or [] if isinstance(g, dict)]
    generato_il = datetime.now(UTC).isoformat(timespec="seconds")
    kpi_md = "\n".join(f"- {k}" for k in fields.get("kpi") or []) or "- Da definire con l'ente"

    report_md = f"""# {titolo}

*Scheda progetto Idea Lab — area {AREAS[req.area]['label'] if req.area else 'n/d'},
territorio {req.territory or 'Puglia'} — ID `{idea_id}` — generata il {generato_il}.*

## In sintesi

**Il problema.** {fields['problema']}

**La soluzione.** {fields['soluzione']}

**Beneficiari.** {fields['beneficiari']}

## Evidenza dai dati

{_sezione_evidenza(datasets, usati)}
## Finanziabilità

{_sezione_finanziabilita(funding, req.area)}
## Gap di dati e come colmarli

{_sezione_gap(datasets, gap_dati)}
## KPI e impatto

{kpi_md}

## Kit di implementazione (per il team di sviluppo)

{_kit_implementazione(fields, datasets, usati, area=req.area, territory=req.territory)}
---
*I dati pubblici possono essere disallineati rispetto alla realtà per tempi
burocratici di pubblicazione: verificare sempre la data di aggiornamento delle
fonti. Le valutazioni di qualità sono calcolate automaticamente dai metadati.*
"""
    return IdeaReportResponse(
        report_md=report_md,
        idea_id=idea_id,
        titolo=titolo,
        generato_il=generato_il,
        offline=offline,
    )
