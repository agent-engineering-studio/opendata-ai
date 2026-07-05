"""Export Markdown embeddabile della scorecard di maturità open-data.

Renderizza il dict prodotto da `build_scorecard` in un documento Markdown
auto-contenuto, pensato per essere incorporato in siti esterni (es. il sito
istituzionale di un Comune). Funzione **pura**: nessun I/O, nessuna dipendenza
LLM/DB — prende la scorecard già serializzata + la base URL pubblica e ritorna
una stringa.

Due scenari:
  - **Dato sufficiente** → riepilogo del livello ODM, 4 dimensioni, copertura
    tematica e raccomandazioni prioritarie, con link alla scheda completa.
  - **Dato insufficiente / assente** → NON si inventano punteggi: si mostra un
    disclaimer di raccomandazione con i *vantaggi* dell'open data, la guida
    operativa passo-passo e i link alla documentazione di OpenData AI per
    avviare una politica di apertura dei dati.
"""

from __future__ import annotations

from typing import Any

# Vantaggi dell'open data mostrati quando un ente non ha (ancora) dati pubblicati.
# Tono costruttivo: spiegano *perché* conviene aprire i dati, non giudicano l'ente.
_VANTAGGI: tuple[tuple[str, str], ...] = (
    ("Trasparenza e fiducia",
     "i dati pubblici aperti rendono verificabili le scelte dell'ente e "
     "rafforzano il rapporto con cittadini e imprese."),
    ("Sviluppo economico del territorio",
     "imprese, startup e ricercatori riusano i dati per creare servizi, app e "
     "analisi: valore che resta sul territorio."),
    ("Efficienza interna",
     "pubblicare una volta in formato aperto riduce le richieste di accesso "
     "ripetute e fa dialogare meglio gli uffici."),
    ("Conformità normativa",
     "l'apertura dei dati attua le Linee guida AGID, il profilo DCAT-AP_IT e "
     "l'obbligo UE sui dataset ad elevato valore (HVD)."),
    ("Decisioni basate sui dati",
     "una base dati aperta e aggiornata abilita analisi, monitoraggio dei "
     "servizi e progettazione di politiche più efficaci."),
)

_DIM_LABEL = {
    "policy": "Politica & governance",
    "portal": "Portale & pubblicazione",
    "quality": "Qualità dei dati",
    "impact": "Impatto & riuso",
}


def _fmt(value: Any) -> str:
    """Punteggio 0–100 con un decimale, robusto a None."""
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _ui(base: str, path: str) -> str:
    return f"{base.rstrip('/')}{path}"


def build_scorecard_markdown(sc: dict[str, Any], *, ui_base_url: str) -> str:
    """Renderizza la scorecard di maturità come Markdown embeddabile.

    `sc` è il dict di `build_scorecard`; `ui_base_url` la base pubblica del
    frontend (per i link a `/maturita` e `/guida-open-data`).
    """
    ent = sc.get("entity", {}) or {}
    name = ent.get("name") or "l'ente"
    entity_id = ent.get("id")
    assessed_at = (sc.get("assessed_at") or "")[:10]
    guida_url = _ui(ui_base_url, "/guida-open-data")
    scheda_url = _ui(ui_base_url, "/maturita")

    lines: list[str] = [f"# Maturità Open Data — {name}", ""]

    if sc.get("insufficient_data"):
        lines += _render_insufficiente(sc, name=name, guida_url=guida_url, scheda_url=scheda_url)
    else:
        lines += _render_scorecard(sc, name=name, assessed_at=assessed_at, scheda_url=scheda_url)

    # Piè di pagina comune: attribuzione + link alla scheda interattiva.
    lines += [
        "",
        "---",
        "",
        (f"_Valutazione generata da **[OpenData AI]({ui_base_url.rstrip('/')})** "
         + (f"il {assessed_at}. " if assessed_at else "")
         + f"[Apri la scheda interattiva]({scheda_url})._"),
    ]
    if entity_id is not None:
        lines.append("")
        lines.append(
            "<!-- Embed: rigenera questo blocco da "
            f"GET /maturity/entities/{entity_id}/scorecard.md -->"
        )
    return "\n".join(lines) + "\n"


def _render_scorecard(
    sc: dict[str, Any], *, name: str, assessed_at: str, scheda_url: str
) -> list[str]:
    level = sc.get("level") or "—"
    overall = _fmt(sc.get("overall"))
    n_datasets = sc.get("n_datasets")
    dims = sc.get("dimensions", {}) or {}

    out: list[str] = [
        f"> **Livello ODM: {level}** · Punteggio complessivo **{overall}/100**"
        + (f" · {n_datasets} dataset valutati" if n_datasets is not None else "")
        + (f" · aggiornato al {assessed_at}" if assessed_at else ""),
        "",
        "## Le quattro dimensioni",
        "",
        "| Dimensione | Punteggio |",
        "| --- | --- |",
    ]
    for key in ("policy", "portal", "quality", "impact"):
        out.append(f"| {_DIM_LABEL[key]} | {_fmt(dims.get(key))}/100 |")

    # Copertura tematica: settori core attesi ma assenti.
    cov = sc.get("coverage") or {}
    missing = [s.get("label") for s in (cov.get("missing_core") or []) if s.get("label")]
    if missing:
        out += [
            "",
            "## Settori da coprire",
            "",
            "Dataset attesi per questo tipo di ente ma non ancora presenti:",
            "",
        ]
        out += [f"- {label}" for label in missing]

    # Raccomandazioni prioritarie (alta severità prima).
    recs = sc.get("recommendations") or []
    order = {"alta": 0, "media": 1, "bassa": 2}
    recs = sorted(recs, key=lambda r: order.get(r.get("severity", "bassa"), 3))
    if recs:
        out += ["", "## Raccomandazioni prioritarie", ""]
        for r in recs[:5]:
            sev = (r.get("severity") or "").strip()
            badge = f"**[{sev}]** " if sev else ""
            out.append(f"- {badge}{r.get('message', '')}")

    # Domanda di riuso non soddisfatta (anello valore⇄maturità).
    unmet = sc.get("unmet_reuse_demand") or {}
    if unmet.get("count"):
        out += [
            "",
            "## Domanda di riuso non soddisfatta",
            "",
            (f"Sono emerse **{unmet['count']}** esigenze di dato dal territorio non "
             "ancora coperte da dataset pubblicati: sono opportunità prioritarie di "
             "apertura."),
        ]

    out += [
        "",
        f"👉 [Apri la scheda di maturità completa di {name}]({scheda_url}) per il "
        "dettaglio delle dimensioni, il trend storico e il confronto con enti simili.",
    ]
    return out


def _render_insufficiente(
    sc: dict[str, Any], *, name: str, guida_url: str, scheda_url: str
) -> list[str]:
    guida = sc.get("guida") or {}
    n_datasets = int(sc.get("n_datasets") or 0)

    if n_datasets == 0:
        premessa = (
            f"Sui cataloghi consultati **non sono stati trovati open data riconducibili "
            f"a {name}**. Non è un giudizio negativo: è il punto di partenza per "
            "costruire una politica di dati aperti che crei valore per il territorio."
        )
    else:
        premessa = (
            f"Per {name} sono stati trovati solo **{n_datasets} dataset valutabili**: "
            "troppo pochi per una valutazione affidabile di maturità. Ecco come "
            "ampliare e rafforzare il patrimonio di open data."
        )

    out: list[str] = [
        "> ⚠️ **Dato insufficiente** — open data non sufficienti per una valutazione.",
        "",
        premessa,
        "",
        "## Perché pubblicare open data",
        "",
    ]
    for titolo, desc in _VANTAGGI:
        out.append(f"- **{titolo}:** {desc}")

    # Guida operativa passo-passo (dalla guidance pura del core).
    passi = guida.get("passi") or []
    if passi:
        out += ["", "## Come partire — guida operativa", ""]
        for p in passi:
            out.append(f"### {p.get('titolo', '')}")
            out.append("")
            out.append(p.get("descrizione", ""))
            out.append("")

    # Documentazione OpenData AI (link assoluti, embeddabili in siti esterni).
    out += [
        "## Documentazione e strumenti",
        "",
        f"- 📘 [Guida completa: avviare una politica di open data]({guida_url}) — "
        "governance, censimento, licenze, metadati DCAT-AP_IT, pubblicazione su "
        "CKAN e federazione con dati.gov.it, passo per passo.",
        f"- 📊 [Verifica la maturità open data del tuo ente]({scheda_url}) — "
        "ricalcola la scorecard appena pubblichi i primi dataset.",
    ]

    # Riferimenti istituzionali (AGID, DCAT-AP_IT, dati.gov.it, HVD, licenze).
    riferimenti = guida.get("riferimenti") or []
    if riferimenti:
        out += ["", "## Riferimenti istituzionali", ""]
        for r in riferimenti:
            label, url = r.get("label"), r.get("url")
            if label and url:
                out.append(f"- [{label}]({url})")

    nota = guida.get("nota")
    if nota:
        out += ["", f"> {nota}"]
    return out
