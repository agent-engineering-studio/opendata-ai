"""Normalizzazione & modello da un CSV (Punto 03 #51, terza voce).

`build_normalization(text)` legge un CSV e genera, in modo deterministico e
senza dipendenze, il passo successivo a "da dato a schema" (`schema.py`):
tabelle di lookup/codici per le colonne categoriali ripetute (DDL + INSERT con
i valori reali), viste SQL di aggregazione (totali per categoria, andamento
per anno) e — quando categoria e data coesistono — una vista pivot che
incrocia le due. Tutto Postgres-flavoured (coerente con `schema.py`), pronto
da eseguire dopo il `CREATE TABLE` generato da `infer_schema`.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Any

from .profile import _cell_type, _date_format, _detect_delimiter, _is_empty
from .schema import _sanitize

# colonne categoriali candidate a lookup: tra 2 e questo numero di valori distinti
_MIN_LOOKUP_DISTINCT = 2
_MAX_LOOKUP_DISTINCT = 50
_MAX_LOOKUP_VALUES_LISTED = 200  # oltre, l'INSERT si genera comunque ma si segnala il volume
_PIVOT_TOP_CATEGORIE = 6


def _quote_sql_literal(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def _year(v: str) -> int | None:
    s = v.strip()
    fmt = _date_format(s)
    if not fmt:
        return None
    if fmt == "yyyy":
        return int(s)
    if fmt.startswith("ISO"):
        return int(s[:4])
    tail = s.replace("/", "-").split("-")[-1]
    if len(tail) == 4 and tail.isdigit():
        return int(tail)
    if len(tail) == 2 and tail.isdigit():
        return 2000 + int(tail)
    return None


def _lookup_table(nome_colonna: str, valori: list[str], used_names: set[str]) -> dict[str, Any]:
    tabella = _sanitize(f"lkp_{nome_colonna}", used_names, 0)
    colonna_fk = _sanitize(f"{nome_colonna}_id", set(), 0)
    ddl = (
        f"CREATE TABLE {tabella} (\n"
        f"    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,\n"
        f"    valore TEXT NOT NULL UNIQUE\n"
        f");"
    )
    valori_elencati = valori[:_MAX_LOOKUP_VALUES_LISTED]
    insert_sql = (
        f"INSERT INTO {tabella} (valore) VALUES\n    "
        + ",\n    ".join(_quote_sql_literal(v) for v in valori_elencati)
        + ";"
    )
    troncato = len(valori) > _MAX_LOOKUP_VALUES_LISTED
    return {
        "colonna_originale": nome_colonna,
        "tabella": tabella,
        "colonna_fk_suggerita": colonna_fk,
        "n_valori": len(valori),
        "valori_troncati": troncato,
        "ddl": ddl,
        "insert_sql": insert_sql,
        "nota": (
            f"Sostituisci «{nome_colonna}» nella tabella principale con «{colonna_fk}» "
            f"(INTEGER REFERENCES {tabella}(id)): elimina refusi/varianti di scrittura e "
            "riduce la dimensione del dato ripetendo un id invece del testo."
            + (f" Elencati solo i primi {_MAX_LOOKUP_VALUES_LISTED} valori distinti su {len(valori)}."
               if troncato else "")
        ),
    }


def build_normalization(text: str, *, table_name: str = "dataset") -> dict[str, Any]:
    """Tabelle di lookup + viste di aggregazione da un CSV.

    Args:
        text: contenuto CSV.
        table_name: nome della tabella principale (per le viste), coerente con
            quello passato a `infer_schema`.

    Returns:
        {"tabelle_lookup": [...], "viste": [...], "note": [...]}.
    """
    note: list[str] = []
    if not text.strip():
        return {"tabelle_lookup": [], "viste": [], "note": ["File vuoto."]}

    text = text.lstrip("﻿")
    delimiter = _detect_delimiter("\n".join(text.splitlines()[:50]))
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if len(rows) < 2:
        return {"tabelle_lookup": [], "viste": [], "note": ["Nessun dato oltre l'intestazione."]}

    header = [h.strip() for h in rows[0]]
    body = rows[1:]
    n_cols = len(header)
    table = _sanitize(table_name, set(), 0) or "dataset"

    tabelle_lookup: list[dict[str, Any]] = []
    viste: list[dict[str, Any]] = []
    used_lookup_names: set[str] = set()
    used_vista_names: set[str] = set()

    categoria_cols: list[tuple[str, list[str]]] = []  # (nome, valori distinti in ordine)
    data_cols: list[str] = []

    for i in range(n_cols):
        nome = header[i] if i < len(header) and header[i] else f"(colonna {i + 1})"
        valori = [r[i] for r in body if i < len(r)]
        non_vuoti = [v.strip() for v in valori if not _is_empty(v)]
        if not non_vuoti:
            continue

        tipi = Counter(_cell_type(v) for v in non_vuoti)
        tipo_dom = tipi.most_common(1)[0][0]

        if tipo_dom == "data":
            data_cols.append(nome)
            anni = Counter(y for y in (_year(v) for v in non_vuoti) if y is not None)
            if anni:
                col_sql = _sanitize(nome, set(), i)
                viste.append({
                    "nome": _sanitize(f"v_andamento_{nome}", used_vista_names, i),
                    "colonna": nome,
                    "tipo": "serie_storica",
                    "ddl": (
                        f"CREATE VIEW v_andamento_{col_sql} AS\n"
                        f"SELECT EXTRACT(YEAR FROM {col_sql}) AS anno, COUNT(*) AS totale\n"
                        f"FROM {table}\nGROUP BY anno\nORDER BY anno;"
                    ),
                })
            continue

        if tipo_dom in ("testo", "booleano"):
            conteggi = Counter(non_vuoti)
            distinti = len(conteggi)
            if _MIN_LOOKUP_DISTINCT <= distinti <= _MAX_LOOKUP_DISTINCT:
                valori_ordinati = [v for v, _ in conteggi.most_common()]
                categoria_cols.append((nome, valori_ordinati))
                if distinti < len(non_vuoti):  # c'è ripetizione: vale la pena normalizzare
                    tabelle_lookup.append(_lookup_table(nome, valori_ordinati, used_lookup_names))
                col_sql = _sanitize(nome, set(), i)
                viste.append({
                    "nome": _sanitize(f"v_totali_{nome}", used_vista_names, i),
                    "colonna": nome,
                    "tipo": "totali_categoria",
                    "ddl": (
                        f"CREATE VIEW v_totali_{col_sql} AS\n"
                        f"SELECT {col_sql}, COUNT(*) AS totale\n"
                        f"FROM {table}\nGROUP BY {col_sql}\nORDER BY totale DESC;"
                    ),
                })

    # ── pivot: categoria × anno, quando entrambe esistono ──
    if categoria_cols and data_cols:
        cat_nome, cat_valori = categoria_cols[0]
        data_nome = data_cols[0]
        top = cat_valori[:_PIVOT_TOP_CATEGORIE]
        col_cat = _sanitize(cat_nome, set(), 0)
        col_data = _sanitize(data_nome, set(), 1)
        used_alias: set[str] = set()
        colonne_pivot = ",\n    ".join(
            f"COUNT(*) FILTER (WHERE {col_cat} = {_quote_sql_literal(v)}) AS {_sanitize(v, used_alias, i)}"
            for i, v in enumerate(top)
        )
        viste.append({
            "nome": _sanitize(f"v_pivot_{cat_nome}_{data_nome}", used_vista_names, 0),
            "colonna": f"{cat_nome} × {data_nome}",
            "tipo": "pivot",
            "ddl": (
                f"CREATE VIEW v_pivot_{col_cat}_{col_data} AS\n"
                f"SELECT EXTRACT(YEAR FROM {col_data}) AS anno,\n    {colonne_pivot}\n"
                f"FROM {table}\nGROUP BY anno\nORDER BY anno;"
            ),
        })
        if len(cat_valori) > _PIVOT_TOP_CATEGORIE:
            note.append(
                f"Il pivot «{cat_nome} × {data_nome}» mostra solo le {_PIVOT_TOP_CATEGORIE} categorie "
                f"più frequenti su {len(cat_valori)} totali."
            )

    if not (tabelle_lookup or viste):
        note.append(
            "Nessuna normalizzazione applicabile: servono colonne categoriali a bassa "
            "cardinalità (per i lookup/le viste) o colonne data (per l'andamento nel tempo)."
        )

    return {"tabelle_lookup": tabelle_lookup, "viste": viste, "note": note}
