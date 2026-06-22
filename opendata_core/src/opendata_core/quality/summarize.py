"""Riepiloghi pronti da un CSV (Punto 03 #51, "Riepiloghi pronti").

`summarize_csv(text)` produce sintesi deterministiche da una tabella: statistiche
delle colonne numeriche, totali per categoria (colonne a bassa cardinalità) e
andamenti nel tempo (conteggi per anno dalle colonne data). Niente LLM, niente
dipendenze: solo ciò che si calcola sul file. Si appoggia ai rilevatori di tipo
di `profile_csv`.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Any

from .profile import (
    _RE_DEC_EN,
    _RE_DEC_IT,
    _RE_INT,
    _RE_INT_THOUSANDS,
    _cell_type,
    _date_format,
    _detect_delimiter,
    _is_empty,
)

# colonne categoriali: tra 2 e questo numero di valori distinti
_MAX_CATEGORIE = 50
_TOP_N = 10


def _to_number(v: str) -> float | None:
    """Numero da una cella, tollerando %, separatori migliaia e virgola decimale IT."""
    s = v.strip().rstrip("%").strip()
    if not s:
        return None
    if _RE_INT.match(s):
        return float(s)
    if _RE_INT_THOUSANDS.match(s):  # 1.234.567 (migliaia all'italiana)
        return float(s.replace(".", ""))
    if _RE_DEC_IT.match(s):         # 1.234,5 / 12,3
        return float(s.replace(".", "").replace(",", "."))
    if _RE_DEC_EN.match(s):         # 12.3
        return float(s)
    return None


def _year(v: str) -> int | None:
    """Anno da una cella data riconosciuta (ISO, dd/mm/yyyy, yyyy…)."""
    s = v.strip()
    fmt = _date_format(s)
    if not fmt:
        return None
    if fmt == "yyyy":
        return int(s)
    if fmt.startswith("ISO"):       # yyyy-mm-dd[...]
        return int(s[:4])
    # dd/mm/yyyy, dd-mm-yyyy → ultimi 4; d/m/yy → secolo 2000
    tail = s.replace("/", "-").split("-")[-1]
    if len(tail) == 4 and tail.isdigit():
        return int(tail)
    if len(tail) == 2 and tail.isdigit():
        return 2000 + int(tail)
    return None


def summarize_csv(text: str, *, max_rows_scan: int = 50000) -> dict[str, Any]:
    """Riepiloghi pronti da un CSV: numerici, categorie e serie temporali."""
    if not text.strip():
        return {"righe": 0, "numeric": [], "categorie": [], "serie_temporali": [], "note": ["File vuoto."]}

    text = text.lstrip("﻿")
    delimiter = _detect_delimiter("\n".join(text.splitlines()[:50]))
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if len(rows) < 2:
        return {"righe": 0, "numeric": [], "categorie": [], "serie_temporali": [],
                "note": ["Nessun dato oltre l'intestazione."]}

    header = [h.strip() for h in rows[0]]
    body = rows[1:max_rows_scan + 1]
    n_cols = len(header)
    note: list[str] = []

    numeric: list[dict[str, Any]] = []
    categorie: list[dict[str, Any]] = []
    serie: list[dict[str, Any]] = []

    for i in range(n_cols):
        nome = header[i] if i < len(header) and header[i] else f"(colonna {i + 1})"
        valori = [r[i] for r in body if i < len(r)]
        non_vuoti = [v for v in valori if not _is_empty(v)]
        if not non_vuoti:
            continue

        tipi = Counter(_cell_type(v) for v in non_vuoti)
        tipo_dom = tipi.most_common(1)[0][0]

        # ── numeriche: statistiche ──
        if tipo_dom in ("intero", "decimale", "percentuale"):
            nums = [n for n in (_to_number(v) for v in non_vuoti) if n is not None]
            if nums:
                tot = sum(nums)
                numeric.append({
                    "column": nome,
                    "conteggio": len(nums),
                    "min": round(min(nums), 4),
                    "max": round(max(nums), 4),
                    "media": round(tot / len(nums), 4),
                    "somma": round(tot, 4),
                })
                continue

        # ── date: andamento per anno ──
        if tipo_dom == "data":
            anni = Counter(y for y in (_year(v) for v in non_vuoti) if y is not None)
            if anni:
                serie.append({
                    "column": nome,
                    "periodo": "anno",
                    "punti": [{"periodo": str(a), "conteggio": c} for a, c in sorted(anni.items())],
                })
                continue

        # ── categoriali (testo/booleano a bassa cardinalità): totali per categoria ──
        conteggi = Counter(v.strip() for v in non_vuoti)
        distinti = len(conteggi)
        if 2 <= distinti <= _MAX_CATEGORIE:
            tot = sum(conteggi.values())
            categorie.append({
                "column": nome,
                "distinti": distinti,
                "top": [
                    {"valore": val, "conteggio": c, "quota_pct": round(100 * c / tot, 1)}
                    for val, c in conteggi.most_common(_TOP_N)
                ],
                "altri": max(0, distinti - _TOP_N),
            })

    if not (numeric or categorie or serie):
        note.append(
            "Nessun riepilogo applicabile: servono colonne numeriche, categoriali "
            "(a bassa cardinalità) o di data."
        )
    return {
        "righe": len(body),
        "numeric": numeric,
        "categorie": categorie,
        "serie_temporali": serie,
        "note": note,
    }
