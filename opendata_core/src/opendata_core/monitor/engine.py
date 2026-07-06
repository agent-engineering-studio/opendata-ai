"""Orchestratore del monitoraggio: combina i controlli in un esito + diff (#88).

`run_checks` prende i dati già raccolti dal runner (nessun I/O qui) e produce
l'esito del run corrente: lista di finding + livello complessivo. `diff_runs`
confronta i finding del run corrente con quelli del run precedente (per codice)
per capire cosa è nuovo, cosa persiste e cosa si è risolto — la base per
decidere se notificare (non ri-notificare un problema già segnalato ieri).
"""

from __future__ import annotations

from typing import Any

from .freshness import check_freshness
from .links import RisultatoLink, check_links
from .quality_regression import check_quality_regression


def run_checks(
    *,
    periodicita: str | None,
    ultimo_aggiornamento_iso: str | None,
    ora_iso: str,
    punteggio_attuale: int | float | None,
    punteggio_precedente: int | float | None,
    link_risultati: list[RisultatoLink] | None = None,
) -> dict[str, Any]:
    """Esegue i tre controlli (freshness/qualità/link) e riassume l'esito.

    Returns:
        {"findings": [...], "esito": "ok"|"attenzione"|"critico"}.
    """
    findings: list[dict[str, Any]] = []

    f = check_freshness(periodicita, ultimo_aggiornamento_iso, ora_iso)
    if f:
        findings.append(f)

    if punteggio_attuale is not None:
        f = check_quality_regression(punteggio_attuale, punteggio_precedente)
        if f:
            findings.append(f)

    findings.extend(check_links(link_risultati or []))

    livelli = {f["livello"] for f in findings}
    esito = "critico" if "alto" in livelli else ("attenzione" if livelli else "ok")
    return {"findings": findings, "esito": esito}


def diff_runs(
    findings_precedenti: list[dict[str, Any]] | None,
    findings_attuali: list[dict[str, Any]],
) -> dict[str, Any]:
    """Confronta due liste di finding (per `codice`): nuovi, risolti, invariati.

    `None` per `findings_precedenti` significa "nessun run precedente": tutto
    ciò che emerge ora è "nuovo", niente è "risolto".
    """
    prec_codici = {f["codice"] for f in (findings_precedenti or [])}
    att_codici = {f["codice"] for f in findings_attuali}
    return {
        "nuovi": [f for f in findings_attuali if f["codice"] not in prec_codici],
        "risolti": sorted(prec_codici - att_codici),
        "invariati": sorted(prec_codici & att_codici),
    }
