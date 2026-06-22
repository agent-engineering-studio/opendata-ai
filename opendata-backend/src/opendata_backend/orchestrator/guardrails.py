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


# ── Requisiti per generatore (modalità idee, Pezzo 8) ──
# Verifiche deterministiche basate sui DOMINI delle evidenze (semplificazione
# dichiarata rispetto alla spec: il controllo "comune ≠ quello in esame" via
# URL sarebbe fragile; il dominio della premessa invece è inequivocabile).
GENERATORI = ("gap_comparativo", "fabbisogno", "incompiuto", "finestra_finanziamento",
              "commercio_duc", "turismo_cultura", "lavoro", "trasporti", "welfare",
              "istruzione", "ambiente", "sanita")

# Generatori del marketing territoriale (modalità marketing, Pezzo 10). A
# differenza dei generatori finanziari, l'ancoraggio non è OpenCoesione ma la
# regola (A)+(B): ogni spunto cita ≥1 premessa LOCALE verificabile (fonte_tipo
# "dato_locale") + ≥1 precedente ESTERNO fetchabile (fonte web → "ispirazione_esterna").
GENERATORI_MARKETING = ("caso_analogo", "asset_sottoutilizzato", "domanda_emergente")

_OC_HOST = "opencoesione.gov.it"
_INDICATORE_HOSTS = ("istat.it", "isprambiente.it", "openstreetmap.org", "overpass-api.de")
# Host validi come premessa di COMMERCIO: imprese ISTAT o densità OSM. ISPRA
# (ambiente) NON è un indicatore di commercio → escluso (evita il loophole).
_COMMERCIO_HOSTS = ("istat.it", "openstreetmap.org", "overpass-api.de")
# Host validi come premessa di TURISMO/CULTURA: asset culturali OSM o ricettività
# ISTAT (capacità esercizi ricettivi — ancora primaria del follow-up).
_TURISMO_HOSTS = ("openstreetmap.org", "overpass-api.de", "istat.it")
# Host valido come premessa di LAVORO: indicatori occupazionali ISTAT 8milaCensus
# (host ottomilacensus.istat.it ⊃ istat.it).
_LAVORO_HOSTS = ("ottomilacensus.istat.it", "istat.it")
# Host valido come premessa di TRASPORTI: densità OSM del trasporto pubblico.
_TRASPORTI_HOSTS = ("openstreetmap.org", "overpass-api.de")
# Host valido come premessa di WELFARE: indici demografici ISTAT DCIS_POPRES1
# (host esploradati.istat.it ⊃ istat.it).
_WELFARE_HOSTS = ("istat.it",)
# Host valido come premessa di ISTRUZIONE: anagrafe scuole MIUR Open Data.
_ISTRUZIONE_HOSTS = ("dati.istruzione.it",)
# Host valido come premessa di AMBIENTE: pericolosità idrogeologica ISPRA IdroGEO
# (host idrogeo.isprambiente.it ⊃ isprambiente.it).
_AMBIENTE_HOSTS = ("isprambiente.it",)
# Host validi come premessa di SANITÀ: farmacie Ministero della Salute + presìdi
# (ospedali/territoriali) mappati su OSM.
_SANITA_HOSTS = ("dati.salute.gov.it", "openstreetmap.org", "overpass-api.de")


def _evidence_hosts(evidenze: list) -> list[str]:
    from urllib.parse import urlparse

    out = []
    for e in evidenze:
        try:
            out.append(urlparse((e.url or "").strip()).netloc.lower())
        except Exception:
            out.append("")
    return out


def _generatore_ok(prop) -> bool:
    """La proposta soddisfa i requisiti minimi di evidenza del suo generatore?

    Per gap_comparativo e incompiuto serve un link a PROGETTO SPECIFICO
    (`/api/progetti/{clp}`), non la pagina generica del dataset: "cosa hanno
    fatto gli altri comuni" deve essere verificabile progetto per progetto
    (feedback del primo collaudo).
    """
    hosts = _evidence_hosts(prop.evidenze)
    urls = [(e.url or "").lower() for e in prop.evidenze]
    has_oc = any(_OC_HOST in h for h in hosts)
    has_oc_project = any(
        _OC_HOST in h and "/progetti/" in u for h, u in zip(hosts, urls)
    )
    if prop.generatore == "gap_comparativo":
        return has_oc_project
    if prop.generatore == "fabbisogno":
        has_indic = any(any(d in h for d in _INDICATORE_HOSTS) for h in hosts)
        return has_indic and has_oc
    if prop.generatore == "incompiuto":
        return has_oc_project
    if prop.generatore == "finestra_finanziamento":
        return any(_OC_HOST in h and "aggregati" in u for h, u in zip(hosts, urls))
    if prop.generatore == "commercio_duc":
        # Lente Commercio/DUC: premessa LOCALE = imprese ISTAT o densità OSM
        # (NON ISPRA: l'ambiente non misura il commercio). Nessun requisito web.
        return any(any(d in h for d in _COMMERCIO_HOSTS) for h in hosts)
    if prop.generatore == "turismo_cultura":
        # Lente Turismo/Cultura: premessa LOCALE = asset culturali OSM o
        # ricettività ISTAT. Nessun requisito web (lo spunto marketing
        # turismo_cultura, web-based, è un'altra cosa).
        return any(any(d in h for d in _TURISMO_HOSTS) for h in hosts)
    if prop.generatore == "lavoro":
        # Lente Lavoro/Competenze: premessa LOCALE = indicatori occupazionali
        # ISTAT 8milaCensus (censimento 2011). Nessun requisito web.
        return any(any(d in h for d in _LAVORO_HOSTS) for h in hosts)
    if prop.generatore == "trasporti":
        # Lente Trasporti/Mobilità: premessa LOCALE = densità OSM del trasporto
        # pubblico. Nessun requisito web.
        return any(any(d in h for d in _TRASPORTI_HOSTS) for h in hosts)
    if prop.generatore == "welfare":
        # Lente Welfare/Coesione sociale: premessa LOCALE = indici demografici
        # ISTAT (DCIS_POPRES1). Nessun requisito web.
        return any(any(d in h for d in _WELFARE_HOSTS) for h in hosts)
    if prop.generatore == "istruzione":
        # Lente Istruzione: premessa LOCALE = dotazione scolastica MIUR Open Data.
        # Nessun requisito web.
        return any(any(d in h for d in _ISTRUZIONE_HOSTS) for h in hosts)
    if prop.generatore == "ambiente":
        # Lente Ambiente/Rischio idrogeologico: premessa LOCALE = pericolosità
        # frane/alluvioni ISPRA IdroGEO. Nessun requisito web.
        return any(any(d in h for d in _AMBIENTE_HOSTS) for h in hosts)
    if prop.generatore == "sanita":
        # Lente Sanità: premessa LOCALE = dotazione farmacie Ministero della Salute.
        # Nessun requisito web.
        return any(any(d in h for d in _SANITA_HOSTS) for h in hosts)
    return False  # generatore mancante o sconosciuto


def _generatore_marketing_ok(prop) -> bool:
    """Lo spunto marketing soddisfa la regola (A)+(B)? (Pezzo 10).

    - generatore ∈ GENERATORI_MARKETING;
    - (A) ≥1 evidenza LOCALE verificabile (fonte_tipo "dato_locale");
    - (B) ≥1 evidenza ESTERNA (fonte web → "ispirazione_esterna").
    Le evidenze qui sono già filtrate a quelle con URL risolvibile, quindi (B)
    implica un precedente esterno effettivamente fetchabile. Manca (A) o (B)
    → lo spunto è scartato (non degradato): senza premessa locale non è
    difendibile, senza precedente esterno non è "marketing che prende spunto".
    """
    if prop.generatore not in GENERATORI_MARKETING:
        return False
    has_local = any(getattr(e, "fonte_tipo", "dato_locale") == "dato_locale" for e in prop.evidenze)
    has_external = any(
        getattr(e, "fonte_tipo", None) == "ispirazione_esterna" for e in prop.evidenze
    )
    return has_local and has_external


def validate_programma(
    resp: "ProgrammaResponse", evidence_urls: set[str], *, modalita: str = "scheda"
) -> "ProgrammaResponse":
    """Applica i guardrail in place e ritorna la risposta ripulita.

    In modalità "idee" si aggiungono i requisiti per generatore: una proposta
    senza `generatore` valido o senza le premesse minime del suo generatore
    viene SCARTATA (la premessa mancante invalida l'inferenza, non la degrada).
    """
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
        if modalita == "idee" and not _generatore_ok(prop):
            log.warning(
                "guardrail idee: proposta %r scartata (generatore %r senza premesse minime)",
                prop.titolo[:40], prop.generatore,
            )
            continue
        if modalita == "marketing" and not _generatore_marketing_ok(prop):
            log.warning(
                "guardrail marketing: spunto %r scartato (generatore %r senza "
                "premessa locale + precedente esterno)",
                prop.titolo[:40], prop.generatore,
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
        # La regola "senza finanziamento → da_verificare" vale per le proposte
        # finanziabili (scheda/idee). Il marketing territoriale NON è ancorato a
        # un fondo: la sua fattibilità riflette la facilità d'azione, non la
        # disponibilità di risorse — quindi questa degradazione NON si applica.
        if (
            modalita != "marketing"
            and prop.finanziamento is None
            and prop.fattibilita.livello != "da_verificare"
        ):
            log.info(
                "guardrail: proposta %r senza finanziamento → fattibilità da_verificare",
                prop.titolo[:40],
            )
            prop.fattibilita.livello = "da_verificare"
        # Marketing: fattibilità mai "alta" su SOLA base esterna — serve un
        # riscontro locale (difesa ridondante: _generatore_marketing_ok già lo
        # impone, ma tiene la regola esplicita per chiarezza/test).
        if (
            modalita == "marketing"
            and prop.fattibilita.livello == "alta"
            and prop.evidenze
            and all(getattr(e, "fonte_tipo", None) == "ispirazione_esterna" for e in prop.evidenze)
        ):
            log.info(
                "guardrail marketing: spunto %r solo esterno → fattibilità degradata a media",
                prop.titolo[:40],
            )
            prop.fattibilita.livello = "media"
        # Tier documentale (spec 09): fattibilità mai "alta" su SOLA base
        # documentale — serve almeno un riscontro certificato.
        if (
            prop.fattibilita.livello == "alta"
            and prop.evidenze
            and all(e.tier == "documentale" for e in prop.evidenze)
        ):
            log.info(
                "guardrail: proposta %r solo documentale → fattibilità degradata a media",
                prop.titolo[:40],
            )
            prop.fattibilita.livello = "media"
        kept_proposte.append(prop)
    resp.proposte = kept_proposte

    # ── Sintesi: stessa euristica anti-persuasione delle voci ──
    hit = _persuasion_hit(resp.sintesi or "")
    if hit:
        log.warning("guardrail: sintesi rimossa (marcatore %r)", hit)
        resp.sintesi = ""

    # ── Disclaimer obbligatorio ──
    if not (resp.disclaimer or "").strip():
        resp.disclaimer = DEFAULT_DISCLAIMER

    return resp
