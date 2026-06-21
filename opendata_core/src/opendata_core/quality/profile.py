"""Profilazione e diagnosi qualità di un CSV — deterministica, senza dipendenze.

`profile_csv(text)` rileva separatore/BOM/encoding-noise, profila ogni colonna
(tipo inferito, % vuoti, distinti, esempi, problemi) e produce una lista di
`findings` azionabili + un `punteggio` 0-100. È la base del "Controllo automatico"
del Data Quality Lab: nessun numero inventato, solo ciò che si misura sul file.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from typing import Any

# ── valori considerati "vuoti" (oltre alla stringa vuota) ────────────────────
_EMPTY_TOKENS = {"", "-", "--", "n/a", "na", "null", "none", "nd", "n.d.", "n.d", "..", "...", "#n/d", "#n/a"}

# ── pattern di tipo (su cella già strip-ata) ─────────────────────────────────
_RE_INT = re.compile(r"^[+-]?\d+$")
_RE_INT_THOUSANDS = re.compile(r"^[+-]?\d{1,3}(\.\d{3})+$")  # 1.234.567 (stile IT)
_RE_DEC_IT = re.compile(r"^[+-]?\d{1,3}(\.\d{3})*,\d+$|^[+-]?\d+,\d+$")  # 1.234,5 / 12,3
_RE_DEC_EN = re.compile(r"^[+-]?\d+\.\d+$")  # 12.3
_RE_BOOL = re.compile(r"^(true|false|vero|falso|si|sì|no|y|n)$", re.IGNORECASE)
_RE_PCT = re.compile(r"^[+-]?\d+([.,]\d+)?\s*%$")

# date: pattern → etichetta del formato (per rilevare formati MISTI nella colonna)
_DATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "ISO yyyy-mm-dd"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"), "ISO datetime"),
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "dd/mm/yyyy"),
    (re.compile(r"^\d{2}-\d{2}-\d{4}$"), "dd-mm-yyyy"),
    (re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$"), "d/m/yy"),
    (re.compile(r"^\d{4}$"), "yyyy"),
]

# header non parlanti (da segnalare)
_RE_GENERIC_HEADER = re.compile(r"^(column|col|campo|field|unnamed|var|colonna)[\s_]?\d*$", re.IGNORECASE)


def _is_empty(v: str) -> bool:
    return v.strip().lower() in _EMPTY_TOKENS


def _date_format(v: str) -> str | None:
    for rx, label in _DATE_PATTERNS:
        if rx.match(v):
            return label
    return None


def _cell_type(v: str) -> str:
    """Tipo di una singola cella non vuota."""
    s = v.strip()
    if _RE_PCT.match(s):
        return "percentuale"
    if _date_format(s):
        return "data"
    if _RE_INT.match(s) or _RE_INT_THOUSANDS.match(s):
        return "intero"
    if _RE_DEC_IT.match(s) or _RE_DEC_EN.match(s):
        return "decimale"
    if _RE_BOOL.match(s):
        return "booleano"
    return "testo"


def _detect_delimiter(sample: str) -> str:
    """Separatore più probabile: Sniffer, con fallback a conteggio sulla 1ª riga."""
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample.splitlines() else ""
        counts = {d: first.count(d) for d in (";", ",", "\t", "|")}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def _finding(livello: str, codice: str, messaggio: str, colonna: str | None = None) -> dict[str, Any]:
    f = {"livello": livello, "codice": codice, "messaggio": messaggio}
    if colonna is not None:
        f["colonna"] = colonna
    return f


# penalità per il punteggio (per finding), per livello
_PENALITA = {"alto": 12, "medio": 6, "basso": 2}


def profile_csv(text: str, *, max_rows_scan: int = 5000, max_examples: int = 3) -> dict[str, Any]:
    """Profila un CSV e restituisce il report di qualità.

    Args:
        text: contenuto CSV.
        max_rows_scan: righe massime profilate (il conteggio totale è esatto).
        max_examples: valori d'esempio per colonna.
    """
    findings: list[dict[str, Any]] = []

    # ── encoding noise / BOM ──
    had_bom = text.startswith("﻿")
    if had_bom:
        text = text.lstrip("﻿")
        findings.append(_finding("basso", "bom", "Il file inizia con un BOM: rimuovilo per massima compatibilità."))
    if "�" in text:
        findings.append(_finding(
            "alto", "encoding",
            "Caratteri illeggibili (�) nel testo: probabile encoding errato — salva il file in UTF-8.",
        ))

    if not text.strip():
        return {
            "format": "CSV", "righe": 0, "colonne": 0, "separatore": None,
            "intestazioni": [], "colonne_profilo": [],
            "findings": [_finding("alto", "vuoto", "Il file è vuoto.")],
            "punteggio": 0,
        }

    sample = "\n".join(text.splitlines()[:50])
    delimiter = _detect_delimiter(sample)

    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not rows:
        return {
            "format": "CSV", "righe": 0, "colonne": 0, "separatore": delimiter,
            "intestazioni": [], "colonne_profilo": [],
            "findings": [_finding("alto", "vuoto", "Nessuna riga leggibile.")],
            "punteggio": 0,
        }

    header = [h.strip() for h in rows[0]]
    body = rows[1:]
    n_cols = len(header)
    n_rows = len(body)

    # ── intestazioni ──
    if not header or all(not h for h in header):
        findings.append(_finding("alto", "header_assente", "Manca la riga di intestazione: la prima riga sembra già un dato."))
    else:
        empties = [i for i, h in enumerate(header) if not h]
        if empties:
            findings.append(_finding("alto", "header_vuoto", f"{len(empties)} colonne senza nome nell'intestazione."))
        dups = [h for h, c in Counter(h for h in header if h).items() if c > 1]
        if dups:
            findings.append(_finding("alto", "header_duplicato", f"Intestazioni duplicate: {', '.join(dups[:5])}."))
        generic = [h for h in header if _RE_GENERIC_HEADER.match(h) or _RE_INT.match(h)]
        if generic:
            findings.append(_finding(
                "medio", "header_non_parlante",
                f"Intestazioni poco descrittive ({', '.join(generic[:5])}): usa nomi chiari e parlanti.",
            ))
        spaced = [h for h in header if h != h.strip() or "  " in h]
        if spaced:
            findings.append(_finding("basso", "header_spazi", "Alcune intestazioni hanno spazi superflui."))

    # ── righe con numero di campi incoerente ──
    ragged = sum(1 for r in body if len(r) != n_cols)
    if ragged:
        findings.append(_finding(
            "alto", "righe_irregolari",
            f"{ragged} righe hanno un numero di colonne diverso dall'intestazione ({n_cols}).",
        ))

    # ── duplicati di riga ──
    seen: set[tuple[str, ...]] = set()
    dup_rows = 0
    for r in body:
        key = tuple(c.strip() for c in r)
        if key in seen:
            dup_rows += 1
        else:
            seen.add(key)
    if dup_rows:
        findings.append(_finding("medio", "righe_duplicate", f"{dup_rows} righe duplicate."))

    # ── profilo per colonna ──
    scan = body[:max_rows_scan]
    colonne_profilo: list[dict[str, Any]] = []
    for i in range(n_cols):
        nome = header[i] if i < len(header) and header[i] else f"(colonna {i + 1})"
        valori = [r[i] for r in scan if i < len(r)]
        non_vuoti = [v for v in valori if not _is_empty(v)]
        n_scan = len(valori)
        vuoti_pct = round(100 * (n_scan - len(non_vuoti)) / n_scan, 1) if n_scan else 100.0

        tipi = Counter(_cell_type(v) for v in non_vuoti)
        tipo_dom = tipi.most_common(1)[0][0] if tipi else "vuoto"
        distinti = len(set(v.strip() for v in non_vuoti))
        esempi = []
        for v in non_vuoti:
            s = v.strip()
            if s not in esempi:
                esempi.append(s)
            if len(esempi) >= max_examples:
                break

        problemi: list[str] = []
        # colonna interamente vuota
        if not non_vuoti:
            problemi.append("colonna interamente vuota")
            findings.append(_finding("medio", "colonna_vuota", "Colonna interamente vuota: rimuovila o popolala.", nome))
        else:
            # troppi vuoti
            if vuoti_pct >= 50:
                findings.append(_finding("alto", "molti_vuoti", f"{vuoti_pct}% di valori mancanti.", nome))
            elif vuoti_pct >= 20:
                findings.append(_finding("medio", "vuoti", f"{vuoti_pct}% di valori mancanti.", nome))
            # tipi misti (il tipo dominante non copre l'85%)
            share = tipi[tipo_dom] / len(non_vuoti)
            if len(tipi) > 1 and share < 0.85:
                problemi.append("tipi misti")
                findings.append(_finding(
                    "medio", "tipi_misti",
                    f"Valori di tipo misto ({', '.join(tipi)}): uniforma il contenuto.", nome,
                ))
            # date in formati misti
            if tipo_dom == "data":
                fmts = {f for f in (_date_format(v.strip()) for v in non_vuoti) if f}
                if len(fmts) > 1:
                    problemi.append("date in formati misti")
                    findings.append(_finding(
                        "medio", "date_miste",
                        f"Date in formati diversi ({', '.join(sorted(fmts))}): usa il formato ISO yyyy-mm-dd.", nome,
                    ))
            # spazi superflui
            if any(v != v.strip() for v in non_vuoti):
                problemi.append("spazi iniziali/finali")
                findings.append(_finding("basso", "spazi", "Valori con spazi iniziali/finali.", nome))
            # decimale stile IT (virgola) → suggerisci punto
            if tipo_dom == "decimale" and any(_RE_DEC_IT.match(v.strip()) for v in non_vuoti):
                findings.append(_finding(
                    "basso", "decimale_virgola",
                    "Decimali con la virgola: per i dati aperti è preferibile il punto.", nome,
                ))

        colonne_profilo.append({
            "nome": nome,
            "tipo": tipo_dom,
            "vuoti_pct": vuoti_pct,
            "distinti": distinti,
            "esempi": esempi,
            "problemi": problemi,
        })

    # ── punteggio ──
    penalita = sum(_PENALITA.get(f["livello"], 0) for f in findings)
    punteggio = max(0, 100 - penalita)

    return {
        "format": "CSV",
        "righe": n_rows,
        "colonne": n_cols,
        "separatore": delimiter,
        "intestazioni": header,
        "righe_profilate": len(scan),
        "colonne_profilo": colonne_profilo,
        "findings": findings,
        "punteggio": punteggio,
    }
