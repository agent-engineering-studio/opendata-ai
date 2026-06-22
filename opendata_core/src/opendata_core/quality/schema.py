"""Da dato a schema — inferenza schema SQL + DDL da un profilo CSV (Punto 03 #51).

`infer_schema(profile)` parte dal report di `profile_csv` (tipi per colonna,
% vuoti, distinti, righe) e propone uno schema relazionale: tipo SQL per colonna,
nullabilità, chiave primaria candidata (o surrogata) e indici utili (date e
colonne categoriali/foreign-key). Emette un `CREATE TABLE` + `CREATE INDEX`
standard. Deterministico, senza dipendenze: "trasforma un file piatto in qualcosa
di ben organizzato e veloce da consultare".
"""

from __future__ import annotations

import re
from typing import Any

# tipo inferito da profile_csv → tipo SQL standard
_SQL_TYPE = {
    "intero": "INTEGER",
    "decimale": "DOUBLE PRECISION",
    "percentuale": "DOUBLE PRECISION",
    "data": "DATE",
    "booleano": "BOOLEAN",
    "testo": "TEXT",
    "vuoto": "TEXT",
}

# nomi che fanno pensare a una chiave/identificatore
_RE_KEY_NAME = re.compile(r"(^|_)(id|codice|cod|code|istat|key|chiave|pk)(_|$)", re.IGNORECASE)

_RESERVED = {
    "select", "from", "where", "table", "order", "group", "index", "user", "default",
    "primary", "key", "and", "or", "not", "null", "create", "drop", "insert", "update",
}


def _sanitize(name: str, used: set[str], fallback_idx: int) -> str:
    """Identificatore SQL sicuro (snake_case, ascii) e univoco."""
    s = name.strip().lower()
    s = re.sub(r"[àá]", "a", s)
    s = re.sub(r"[èé]", "e", s)
    s = re.sub(r"[ìí]", "i", s)
    s = re.sub(r"[òó]", "o", s)
    s = re.sub(r"[ùú]", "u", s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if not s or s[0].isdigit():
        s = f"col_{fallback_idx}" if not s else f"c_{s}"
    if s in _RESERVED:
        s = f"{s}_col"
    base, n = s, 2
    while s in used:
        s = f"{base}_{n}"
        n += 1
    used.add(s)
    return s


def infer_schema(profile: dict[str, Any], *, table_name: str = "dataset") -> dict[str, Any]:
    """Inferisce schema SQL + DDL dal profilo di un CSV.

    Args:
        profile: output di `profile_csv` (serve `colonne_profilo` e `righe`).
        table_name: nome tabella desiderato (sanificato come identificatore SQL).
    """
    cols_profile = profile.get("colonne_profilo") or []
    n_rows = int(profile.get("righe") or 0)

    table = _sanitize(table_name, set(), 0) or "dataset"
    notes: list[str] = []

    used: set[str] = set()
    columns: list[dict[str, Any]] = []
    for idx, c in enumerate(cols_profile, start=1):
        tipo = c.get("tipo", "testo")
        sql_type = _SQL_TYPE.get(tipo, "TEXT")
        vuoti = float(c.get("vuoti_pct") or 0.0)
        distinti = int(c.get("distinti") or 0)
        nome_orig = str(c.get("nome", f"col_{idx}"))
        col = {
            "name": _sanitize(nome_orig, used, idx),
            "original": nome_orig,
            "sql_type": sql_type,
            "nullable": vuoti > 0.0,
            "distinct": distinti,
            "is_primary_key": False,
            "note": None,
        }
        if tipo == "percentuale":
            col["note"] = "valori con '%': rimuovere il simbolo prima del caricamento"
        elif tipo == "vuoto":
            col["note"] = "colonna interamente vuota: valuta se rimuoverla"
        columns.append(col)

    # ── chiave primaria: colonna univoca, senza vuoti; preferisci nomi 'id-like' ──
    pk_candidates = [
        col for col in columns
        if not col["nullable"] and n_rows > 0 and col["distinct"] == n_rows
    ]
    pk: str | None = None
    surrogate = False
    if pk_candidates:
        named = [c for c in pk_candidates if _RE_KEY_NAME.search(c["original"])]
        chosen = (named or pk_candidates)[0]
        chosen["is_primary_key"] = True
        pk = chosen["name"]
    elif columns:
        surrogate = True
        notes.append(
            "Nessuna colonna univoca adatta a chiave primaria: aggiunta una chiave "
            "surrogata 'id' autogenerata."
        )

    # ── indici: date (serie storiche) + categoriali/foreign-key (filtri/join) ──
    indexes: list[dict[str, str]] = []
    cat_threshold = max(20, int(n_rows * 0.05)) if n_rows else 20
    for col in columns:
        if col["is_primary_key"]:
            continue
        reason: str | None = None
        if col["sql_type"] == "DATE":
            reason = "colonna temporale: utile per filtri e serie storiche"
        elif _RE_KEY_NAME.search(col["original"]):
            reason = "sembra un codice/identificatore: utile per join e ricerche"
        elif col["sql_type"] == "TEXT" and 0 < col["distinct"] <= cat_threshold:
            reason = "bassa cardinalità (categoriale): utile per raggruppamenti e filtri"
        if reason:
            indexes.append({"column": col["name"], "reason": reason})

    ddl = _build_ddl(table, columns, pk, surrogate, indexes)
    return {
        "table_name": table,
        "row_estimate": n_rows,
        "columns": [
            {k: v for k, v in col.items() if k != "distinct"} for col in columns
        ],
        "primary_key": pk,
        "surrogate_key": surrogate,
        "indexes": indexes,
        "ddl": ddl,
        "notes": notes,
    }


def _build_ddl(
    table: str,
    columns: list[dict[str, Any]],
    pk: str | None,
    surrogate: bool,
    indexes: list[dict[str, str]],
) -> str:
    lines: list[str] = [f"CREATE TABLE {table} ("]
    body: list[str] = []
    if surrogate:
        body.append("    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY")
    for col in columns:
        parts = [f"    {col['name']}", col["sql_type"]]
        if not col["nullable"]:
            parts.append("NOT NULL")
        if col["is_primary_key"]:
            parts.append("PRIMARY KEY")
        line = " ".join(parts)
        if col.get("note"):
            line += f"  -- {col['note']}"
        body.append(line)
    lines.append(",\n".join(body))
    lines.append(");")
    ddl = "\n".join(lines)
    if indexes:
        idx_lines = [
            f"CREATE INDEX idx_{table}_{ix['column']} ON {table} ({ix['column']});"
            for ix in indexes
        ]
        ddl += "\n\n" + "\n".join(idx_lines)
    return ddl
