"""Gate di qualità dei report territoriali — motore PURO, comune-agnostico.

Nessun FastMCP/FastAPI/LLM, nessuna fonte live, nessun I/O, nessun letterale
specifico di un comune: i gate operano SOLO sul testo del report + i metadati
INIETTATI dal chiamante (popolazione di riferimento, anno corrente, testo delle
evidenze, disponibilità del dato vincoli). Derivano dalla rubric "Qualità dei
report territoriali" (Documento di metodo Parte IV) e intercettano i 5 difetti
ricorrenti osservati nella revisione dei report reali:

  1. Attualità del dato      — Censimento 2011/indicatori vecchi spacciati per attuali
  2. Coerenza denominatori   — più popolazioni di riferimento diverse nello stesso report
  6. Verifica fattuale       — certificazioni (DOP/IGP/DOC…) non riscontrate nelle evidenze
 10. Non ridondanza          — proposte duplicate tra sezioni
  8. Verifica vincoli        — PAI/vincoli rinviati a "da verificare" invece di riportare l'esito

Ogni gate restituisce un `Finding` PASS/WARN/FAIL. `valuta_report` aggrega e
calcola un punteggio rubric parziale (le 5 dimensioni valutabili in automatico).
Non blocca: il chiamante annota il report col footer e applica le correzioni
deterministiche a monte (grounding dei prompt)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

Esito = Literal["PASS", "WARN", "FAIL"]
Tipo = Literal["critica", "alta", "media"]

# Soglia di "dato non più attuale" (anni): oltre, l'indicatore va etichettato storico.
FRESHNESS_MAX_ETA = 4
# Soglia rubric (parziale) consigliata per pubblicare senza revisione.
SOGLIA_PUBBLICAZIONE = 8  # su 10 (5 dimensioni × 2)


@dataclass
class Finding:
    gate: str
    dimensione: str
    tipo: Tipo
    esito: Esito
    messaggio: str

    @property
    def punti(self) -> int:
        return {"PASS": 2, "WARN": 1, "FAIL": 0}[self.esito]


@dataclass
class QualitaReport:
    findings: list[Finding] = field(default_factory=list)

    @property
    def punteggio(self) -> int:
        return sum(f.punti for f in self.findings)

    @property
    def massimo(self) -> int:
        return 2 * len(self.findings)

    @property
    def esito(self) -> Esito:
        """FAIL se una dimensione CRITICA fallisce (impedisce la pubblicazione
        anche con punteggio alto); altrimenti WARN se c'è almeno un WARN/FAIL."""
        if any(f.tipo == "critica" and f.esito == "FAIL" for f in self.findings):
            return "FAIL"
        if any(f.esito in ("WARN", "FAIL") for f in self.findings):
            return "WARN"
        return "PASS"

    @property
    def pubblicabile(self) -> bool:
        return self.esito != "FAIL" and self.punteggio >= SOGLIA_PUBBLICAZIONE

    def to_dict(self) -> dict[str, object]:
        return {
            "punteggio": self.punteggio,
            "massimo": self.massimo,
            "dimensioni_valutate": len(self.findings),
            "esito": self.esito,
            "pubblicabile": self.pubblicabile,
            "controlli": [
                {
                    "gate": f.gate,
                    "dimensione": f.dimensione,
                    "tipo": f.tipo,
                    "esito": f.esito,
                    "messaggio": f.messaggio,
                }
                for f in self.findings
            ],
        }

    def markdown(self) -> str:
        """Footer compatto "Qualità del report" da appendere al disclaimer."""
        icona = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}
        righe = [
            f"**Qualità del report** — {self.punteggio}/{self.massimo} "
            f"({len(self.findings)}/13 dimensioni valutate automaticamente) · esito {self.esito}",
        ]
        for f in self.findings:
            righe.append(f"- {icona[f.esito]} {f.dimensione}: {f.messaggio}")
        return "\n".join(righe)


# ── Utilità di normalizzazione testo ────────────────────────────────


def _norm(s: str) -> str:
    """Lowercase + rimozione accenti, per confronti robusti."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def _join(testi: list[str]) -> str:
    return "\n".join(t for t in testi if t)


# ── Gate 1 — Attualità del dato (freshness) ─────────────────────────

_CENSIMENTO_2011 = re.compile(r"censimento\s+(?:della\s+popolazione\s+)?2011", re.I)
_STORICO = re.compile(r"storic[oa]|d'epoca|del passato", re.I)
# Anno-vintage citato accanto a un riferimento al dato (ISTAT/dati/fonte/anno…).
_DATA_YEAR = re.compile(
    r"(?:istat|dati|fonte|censimento|anno|aggiornat\w+|rilevazione)\D{0,24}\b(19\d\d|20[0-3]\d)\b",
    re.I,
)


def _etichettato_storico(text: str, pos: int, *, finestra: int = 30) -> bool:
    """True se l'occorrenza a `pos` è acknowledged come storica (etichetta vicina)."""
    return bool(_STORICO.search(text[max(0, pos - finestra): pos + finestra]))


def gate_freshness(testi: list[str], *, anno_corrente: int) -> Finding:
    text = _join(testi)
    soglia = anno_corrente - FRESHNESS_MAX_ETA
    m2011 = _CENSIMENTO_2011.search(text)
    if m2011 and not _etichettato_storico(text, m2011.start()):
        return Finding(
            "freshness", "1. Attualità del dato", "critica", "FAIL",
            "Censimento 2011 citato come attuale: usare il Censimento Permanente "
            "o etichettare 'dato storico 2011'.",
        )
    vecchi = sorted({
        int(m.group(1)) for m in _DATA_YEAR.finditer(text)
        if int(m.group(1)) < soglia and not _etichettato_storico(text, m.start(1))
    })
    if vecchi:
        return Finding(
            "freshness", "1. Attualità del dato", "critica", "WARN",
            f"indicatori con annualità ≤ {soglia} ({', '.join(map(str, vecchi))}): "
            "verificare che non siano presentati come attuali.",
        )
    return Finding("freshness", "1. Attualità del dato", "critica", "PASS",
                   "nessun dato palesemente datato presentato come attuale.")


# ── Gate 2 — Coerenza denominatori (popolazione unica) ──────────────

# "27.889 ab", "26 731 abitanti", "27889 residenti" — richiede il suffisso
# popolazione, così i conteggi (posti letto, fermate…) non danno falsi positivi.
_POP_FIGURE = re.compile(
    r"\b(\d{1,3}(?:[. \s]\d{3})+|\d{4,7})\s*(?:ab\.?|abitanti|residenti)\b",
    re.I,
)


def _to_int(token: str) -> int:
    return int(re.sub(r"[. \s]", "", token))


def gate_denominatore(testi: list[str], *, pop_rif: int | None) -> Finding:
    valori = {_to_int(m.group(1)) for m in _POP_FIGURE.finditer(_join(testi))}
    if not valori:
        return Finding("denominatore", "2. Coerenza denominatori", "critica", "PASS",
                       "nessuna cifra di popolazione esplicita da verificare.")
    if len(valori) > 1:
        return Finding(
            "denominatore", "2. Coerenza denominatori", "critica", "FAIL",
            f"popolazioni di riferimento diverse nel report ({', '.join(map(str, sorted(valori)))}): "
            "usare un unico denominatore (l'anagrafica più recente).",
        )
    unico = next(iter(valori))
    if pop_rif is not None and unico != pop_rif:
        return Finding(
            "denominatore", "2. Coerenza denominatori", "critica", "WARN",
            f"popolazione citata ({unico}) diversa dal riferimento iniettato ({pop_rif}).",
        )
    return Finding("denominatore", "2. Coerenza denominatori", "critica", "PASS",
                   "popolazione di riferimento coerente.")


# ── Gate 6 — Verifica fattuale (certificazioni DOP/IGP/DOC…) ─────────

_CERT = re.compile(r"\b(DOP|IGP|DOCG|DOC|STG)\b")


def gate_certificazioni(testi: list[str], *, evidenze_testo: str) -> Finding:
    text = _join(testi)
    sigle = {m.group(1) for m in _CERT.finditer(text)}
    if not sigle:
        return Finding("certificazioni", "6. Verifica fattuale", "critica", "PASS",
                       "nessuna certificazione di origine da verificare.")
    ev = _norm(evidenze_testo)
    # Se nessuna delle sigle citate compare nelle evidenze iniettate, la
    # certificazione non è riscontrata da fonte → declassa a "da verificare".
    riscontrate = any(s.lower() in ev for s in sigle)
    if not riscontrate:
        return Finding(
            "certificazioni", "6. Verifica fattuale", "critica", "WARN",
            f"certificazioni citate ({', '.join(sorted(sigle))}) non riscontrate nelle "
            "evidenze: validare su registro ufficiale (MASAF / EU eAmbrosia) o "
            "etichettare 'da verificare'.",
        )
    return Finding("certificazioni", "6. Verifica fattuale", "critica", "PASS",
                   "certificazioni citate riscontrate nelle evidenze.")


# ── Gate 10 — Non ridondanza (proposte duplicate) ───────────────────

_STOPWORDS = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "del", "della",
    "dei", "delle", "e", "ed", "a", "ad", "da", "in", "con", "su", "per", "tra",
    "fra", "sistema", "integrato", "comune", "nuovo", "nuova", "piano", "progetto",
}


def _keywords(titolo: str) -> set[str]:
    return {w for w in re.findall(r"[a-zàèéìòù]{4,}", _norm(titolo)) if w not in _STOPWORDS}


def gate_dedup(titoli_proposte: list[str]) -> Finding:
    titoli = [t for t in titoli_proposte if t and t.strip()]
    coppie: list[tuple[str, str]] = []
    for i in range(len(titoli)):
        ki = _keywords(titoli[i])
        for j in range(i + 1, len(titoli)):
            kj = _keywords(titoli[j])
            if not ki or not kj:
                continue
            jacc = len(ki & kj) / len(ki | kj)
            if jacc >= 0.5:
                coppie.append((titoli[i], titoli[j]))
    if coppie:
        esempi = "; ".join(f"«{a}» ~ «{b}»" for a, b in coppie[:3])
        return Finding(
            "dedup", "10. Non ridondanza", "alta", "WARN",
            f"possibili proposte duplicate da consolidare nel portafoglio: {esempi}.",
        )
    return Finding("dedup", "10. Non ridondanza", "alta", "PASS",
                   "nessuna proposta palesemente duplicata.")


# ── Gate 8 — Verifica vincoli (PAI/ISPRA rinviato) ──────────────────

_VINCOLO_CTX = re.compile(r"pai|idrogeolog|vincol|ispra|alluvion|peric", re.I)
_RINVIO = re.compile(r"da\s+verificar|da\s+calcolar|da\s+definir|non\s+disponibil", re.I)


def gate_vincoli(testi: list[str], *, vincolo_comunale_disponibile: bool) -> Finding:
    text = _join(testi)
    # Cerca un rinvio ("da verificare") in una frase che parla di vincoli/PAI.
    rinviato = any(
        _VINCOLO_CTX.search(frase) and _RINVIO.search(frase)
        for frase in re.split(r"[.\n;]", text)
    )
    if rinviato and vincolo_comunale_disponibile:
        return Finding(
            "vincoli", "8. Verifica vincoli", "alta", "WARN",
            "vincoli idrogeologici rinviati a 'da verificare' pur essendo disponibile "
            "l'esito ISPRA a livello comunale: riportare l'esito (es. % in P2/P3).",
        )
    return Finding("vincoli", "8. Verifica vincoli", "alta", "PASS",
                   "esito vincoli riportato o non applicabile.")


# ── Aggregatore ─────────────────────────────────────────────────────


def valuta_report(
    *,
    testi: list[str],
    titoli_proposte: list[str],
    pop_rif: int | None,
    anno_corrente: int,
    evidenze_testo: str = "",
    vincolo_comunale_disponibile: bool = False,
) -> QualitaReport:
    """Esegue i 5 gate auto-valutabili (Fase 1) e restituisce la scorecard.

    Tutti gli input sono primitivi iniettati dal chiamante → comune-agnostico e
    puro. Il chiamante (backend) estrae `testi`/`titoli`/`evidenze_testo` dalla
    `ProgrammaResponse` strutturata e passa popolazione/anno del comune."""
    return QualitaReport(findings=[
        gate_freshness(testi, anno_corrente=anno_corrente),
        gate_denominatore(testi, pop_rif=pop_rif),
        gate_certificazioni(testi, evidenze_testo=evidenze_testo),
        gate_dedup(titoli_proposte),
        gate_vincoli(testi, vincolo_comunale_disponibile=vincolo_comunale_disponibile),
    ])
