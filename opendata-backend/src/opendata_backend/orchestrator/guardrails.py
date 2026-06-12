"""FactChecker deterministico della scheda programma (spec 04).

Nessuna chiamata LLM: regole pure applicate DOPO il programma_agent.
  - ogni voce SWOT / proposta deve citare ≥1 evidenza con URL realmente
    raccolta dagli specialisti → le voci orfane vengono SCARTATE, mai inventate;
  - una proposta senza evidenza di finanziamento non può dichiarare una linea
    di finanziamento e la sua fattibilità degrada a "da_verificare";
  - il disclaimer è obbligatorio (iniettato se assente);
  - euristica anti-persuasione conservativa: voci/proposte con marcatori da
    campagna elettorale vengono rimosse (meglio scartare che lasciar passare).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # import solo per i tipi: programma.py importa questo modulo
    from .programma import ProgrammaResponse

log = logging.getLogger("orchestrator.guardrails")

DEFAULT_DISCLAIMER = (
    "Analisi generata automaticamente a partire da dati pubblici (ISTAT, "
    "OpenCoesione e altre fonti aperte citate). Ogni affermazione è ancorata "
    "alle fonti indicate; le proposte sono ipotesi di lavoro da verificare "
    "con gli uffici competenti, non impegni né materiale elettorale."
)

# Marcatori da campagna: esortazioni di voto, attacchi, superlativi non
# supportati, promesse in prima persona plurale. Volutamente conservativi:
# un falso positivo costa una voce, un falso negativo costa la credibilità.
_PERSUASION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bvota(?:te|teci|re per)?\b",
        r"\belegg(?:ete|eteci|imi)\b",
        r"\bcampagna elettorale\b",
        r"\bavversari\w*\b",
        r"\bopposizion\w+\b",
        r"\bpromett(?:o|iamo)\b",
        r"\bgarantiamo\b",
        r"\binsieme (?:possiamo|ce la faremo)\b",
        r"\bsolo noi\b",
        r"\bstraordinari\w*\b",
        r"\brivoluzionari\w*\b",
        r"\bsenza precedenti\b",
        r"\bil migliore .{0,30}(?:di sempre|d'italia)\b",
    )
)


def _persuasion_hit(text: str) -> str | None:
    for pat in _PERSUASION_PATTERNS:
        m = pat.search(text or "")
        if m:
            return m.group(0)
    return None


def _has_resolvable_evidence(evidenze: list, evidence_urls: set[str]) -> bool:
    return any((e.url or "").strip() in evidence_urls for e in evidenze)


def validate_programma(resp: "ProgrammaResponse", evidence_urls: set[str]) -> "ProgrammaResponse":
    """Applica i guardrail in place e ritorna la risposta ripulita."""
    urls = {u.strip() for u in evidence_urls}

    # ── SWOT: scarta voci orfane o persuasive ──
    for key, voci in resp.swot.items():
        kept = []
        for voce in voci:
            hit = _persuasion_hit(voce.testo)
            if hit:
                log.warning("guardrail: voce SWOT '%s' rimossa (marcatore %r)", key, hit)
                continue
            voce.evidenze = [e for e in voce.evidenze if (e.url or "").strip() in urls]
            if not voce.evidenze:
                log.warning(
                    "guardrail: voce SWOT '%s' senza evidenza risolvibile scartata: %.60s",
                    key, voce.testo,
                )
                continue
            kept.append(voce)
        resp.swot[key] = kept

    # ── Proposte ──
    kept_proposte = []
    for prop in resp.proposte:
        hit = _persuasion_hit(f"{prop.titolo} {prop.descrizione}")
        if hit:
            log.warning("guardrail: proposta %r rimossa (marcatore %r)", prop.titolo[:40], hit)
            continue
        prop.evidenze = [e for e in prop.evidenze if (e.url or "").strip() in urls]
        if not prop.evidenze:
            log.warning(
                "guardrail: proposta %r senza evidenza risolvibile scartata", prop.titolo[:60]
            )
            continue
        # Linea di finanziamento dichiarabile solo con fonte raccolta davvero.
        if prop.finanziamento is not None and (
            (prop.finanziamento.fonte_url or "").strip() not in urls
        ):
            log.warning(
                "guardrail: finanziamento di %r senza fonte risolvibile → rimosso",
                prop.titolo[:40],
            )
            prop.finanziamento = None
        if prop.finanziamento is None and prop.fattibilita.livello != "da_verificare":
            log.info(
                "guardrail: proposta %r senza finanziamento → fattibilità da_verificare",
                prop.titolo[:40],
            )
            prop.fattibilita.livello = "da_verificare"
        kept_proposte.append(prop)
    resp.proposte = kept_proposte

    # ── Disclaimer obbligatorio ──
    if not (resp.disclaimer or "").strip():
        resp.disclaimer = DEFAULT_DISCLAIMER

    return resp
