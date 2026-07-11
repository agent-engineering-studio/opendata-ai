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


_RANK_LIVELLO = {"basso": 1, "medio": 2, "alto": 3}


def _rank(livello: Any) -> int:
    return _RANK_LIVELLO.get(livello, 0)


def diff_runs(
    findings_precedenti: list[dict[str, Any]] | None,
    findings_attuali: list[dict[str, Any]],
) -> dict[str, Any]:
    """Confronta due liste di finding (per `codice`): nuovi, aggravati, risolti, invariati.

    `None` per `findings_precedenti` significa "nessun run precedente": tutto
    ciò che emerge ora è "nuovo", niente è "risolto".

    `aggravati` sono i finding il cui `codice` c'era già ma la cui severità è
    salita (es. `medio`→`alto`): un problema noto che è peggiorato vale una nuova
    notifica, altrimenti un calo di maturità che si approfondisce resterebbe muto
    finché non cambia codice. È un sottoinsieme di `invariati`.
    """
    prec_rank: dict[str, int] = {}
    for f in findings_precedenti or []:
        codice = f["codice"]
        prec_rank[codice] = max(prec_rank.get(codice, 0), _rank(f.get("livello")))
    prec_codici = set(prec_rank)
    att_codici = {f["codice"] for f in findings_attuali}
    return {
        "nuovi": [f for f in findings_attuali if f["codice"] not in prec_codici],
        "aggravati": [
            f for f in findings_attuali
            if f["codice"] in prec_rank and _rank(f.get("livello")) > prec_rank[f["codice"]]
        ],
        "risolti": sorted(prec_codici - att_codici),
        "invariati": sorted(prec_codici & att_codici),
    }
