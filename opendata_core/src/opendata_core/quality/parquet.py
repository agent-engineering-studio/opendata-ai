"""Convertitore CSV → Parquet (Punto #101, "convertitori avanzati").

`csv_to_parquet(text)` trasforma un CSV in un file Parquet colonnare e compresso,
completando il consiglio "Veloce anche quando è grande" di `advise_scale`: lì si
*suggerisce* il formato colonnare, qui lo si *produce*. I tipi delle colonne sono
inferiti con le stesse regole del profilo (`_cell_type`) e una colonna viene
tipizzata (intero/decimale/booleano) solo se TUTTI i valori non vuoti vi
aderiscono — altrimenti resta testo, senza perdita di dati. Deterministico.

Unico modulo del Quality Lab con una dipendenza esterna: `pyarrow`, importato
pigramente e dichiarato nell'extra opzionale `converters`. Senza pyarrow la
funzione non solleva: restituisce `ok=False` con un messaggio chiaro.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Any

from .profile import _cell_type, _detect_delimiter, _is_empty

# valori booleani riconosciuti (coerenti con _RE_BOOL del profilo)
_BOOL_TRUE = {"true", "vero", "si", "sì", "y"}
_BOOL_FALSE = {"false", "falso", "no", "n"}

# tipi di cella che tipizziamo in Parquet; gli altri (data, percentuale, testo)
# restano stringhe: nessuna conversione rischiosa, nessun dato inventato.
_TYPED = {"intero", "decimale", "booleano"}


def _parse_int(s: str) -> int:
    # 1.234.567 (migliaia stile IT) → 1234567
    return int(s.replace(".", ""))


def _parse_float(s: str) -> float:
    # 1.234,5 → 1234.5 ; 12,3 → 12.3 ; 12.3 resta 12.3
    # In una colonna decimale può comparire un valore intero: segue le regole
    # dell'intero ("1.234" = milleduecentotrentaquattro, stile IT).
    if _cell_type(s) == "intero":
        return float(_parse_int(s))
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def _column_type(values: list[str]) -> str:
    """Tipo della colonna: tipizzata solo se tutti i valori non vuoti aderiscono."""
    non_empty = [v.strip() for v in values if not _is_empty(v)]
    if not non_empty:
        return "testo"
    tipi = Counter(_cell_type(v) for v in non_empty)
    dominante = tipi.most_common(1)[0][0]
    if dominante not in _TYPED or len(tipi) > 1:
        # interi mischiati a decimali sono comunque numeri: promuovi a decimale
        if set(tipi) == {"intero", "decimale"}:
            return "decimale"
        return "testo"
    return dominante


def _dedup_headers(header: list[str]) -> tuple[list[str], list[str]]:
    """Nomi colonna unici e non vuoti (Parquet li richiede). Ritorna (nomi, warnings)."""
    out: list[str] = []
    warnings: list[str] = []
    seen: dict[str, int] = {}
    for i, h in enumerate(header):
        name = h.strip() or f"colonna_{i + 1}"
        if not h.strip():
            warnings.append(f"Colonna {i + 1} senza nome: rinominata in '{name}'.")
        if name in seen:
            seen[name] += 1
            new = f"{name}_{seen[name]}"
            warnings.append(f"Intestazione duplicata '{name}': rinominata in '{new}'.")
            name = new
        else:
            seen[name] = 1
        out.append(name)
    return out, warnings


def csv_to_parquet(text: str) -> dict[str, Any]:
    """Converte un CSV in Parquet (compressione snappy).

    Ritorna `content` (bytes del file Parquet), lo schema delle colonne con i
    tipi applicati e le dimensioni prima/dopo. Con `ok=False` il campo `error`
    spiega il motivo (file vuoto, pyarrow assente, ...).
    """
    vuoto = {
        "ok": False, "content": None, "righe": 0, "colonne": 0, "schema": [],
        "dimensione_csv": 0, "dimensione_parquet": 0, "riduzione_pct": None,
        "warnings": [],
    }
    if not text.strip():
        return {**vuoto, "error": "Il file è vuoto."}

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return {**vuoto, "error": (
            "Esportazione Parquet non disponibile su questo server: manca la "
            "dipendenza opzionale pyarrow (extra 'converters')."
        )}

    text = text.lstrip("﻿")
    delimiter = _detect_delimiter("\n".join(text.splitlines()[:50]))
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not rows or not any(c.strip() for c in rows[0]):
        return {**vuoto, "error": "Nessuna riga leggibile.", "warnings": []}

    header, warnings = _dedup_headers([h.strip() for h in rows[0]])
    n_cols = len(header)
    body = rows[1:]
    ragged = sum(1 for r in body if len(r) != n_cols)
    if ragged:
        warnings.append(
            f"{ragged} righe con un numero di colonne diverso dall'intestazione: "
            "completate con valori vuoti o troncate."
        )

    columns: list[list[str]] = [
        [r[i] if i < len(r) else "" for r in body] for i in range(n_cols)
    ]
    tipi = [_column_type(col) for col in columns]

    arrays = []
    for col, tipo in zip(columns, tipi):
        if tipo == "intero":
            arrays.append(pa.array(
                [None if _is_empty(v) else _parse_int(v.strip()) for v in col],
                type=pa.int64(),
            ))
        elif tipo == "decimale":
            arrays.append(pa.array(
                [None if _is_empty(v) else _parse_float(v.strip()) for v in col],
                type=pa.float64(),
            ))
        elif tipo == "booleano":
            arrays.append(pa.array(
                [None if _is_empty(v) else v.strip().lower() in _BOOL_TRUE for v in col],
                type=pa.bool_(),
            ))
        else:
            arrays.append(pa.array(
                [None if _is_empty(v) else v.strip() for v in col],
                type=pa.string(),
            ))

    table = pa.Table.from_arrays(arrays, names=header)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    content = buf.getvalue()

    dim_csv = len(text.encode("utf-8"))
    riduzione = round(100 * (1 - len(content) / dim_csv), 1) if dim_csv else None
    return {
        "ok": True,
        "error": None,
        "content": content,
        "righe": len(body),
        "colonne": n_cols,
        "schema": [{"nome": n, "tipo": t} for n, t in zip(header, tipi)],
        "dimensione_csv": dim_csv,
        "dimensione_parquet": len(content),
        "riduzione_pct": riduzione,
        "warnings": warnings,
    }
