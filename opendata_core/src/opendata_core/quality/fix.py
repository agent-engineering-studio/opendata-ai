"""Auto-fix di un CSV — correzioni SICURE e deterministiche (Data Quality Lab #49).

`fix_csv(text)` applica solo trasformazioni che non perdono né alterano il
significato del dato: rimozione BOM, intestazioni ripulite (trim/dedup/riempite),
spazi superflui nelle celle, date `gg/mm/aaaa` → ISO `aaaa-mm-gg`, decimali con la
virgola → punto, e riscrittura in UTF-8 con separatore virgola (standard open
data). Restituisce il file corretto + l'elenco delle modifiche. Volutamente NON
tocca casi ambigui (es. "1.234" senza virgola: migliaia o decimale?).
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from typing import Any

from .profile import _RE_DEC_IT, _cell_type, _detect_delimiter, _is_empty

_BOM = "﻿"
# gg/mm/aaaa o gg-mm-aaaa → ISO (assunzione giorno-mese, contesto italiano).
_RE_DMY = re.compile(r"^(\d{2})[/-](\d{2})[/-](\d{4})$")


def _to_iso(s: str) -> str | None:
    m = _RE_DMY.match(s)
    if not m:
        return None
    d, mo, y = m.group(1), m.group(2), m.group(3)
    if 1 <= int(d) <= 31 and 1 <= int(mo) <= 12:
        return f"{y}-{mo}-{d}"
    return None


def _it_decimal_to_dot(s: str) -> str:
    """'1.234,56' → '1234.56' · '12,3' → '12.3' (s già matchato da _RE_DEC_IT)."""
    return s.replace(".", "").replace(",", ".")


def _fix_headers(header: list[str]) -> tuple[list[str], int]:
    """Trim + collassa spazi + riempi i vuoti + deduplica. Ritorna (header, n_modificati)."""
    out: list[str] = []
    used: Counter[str] = Counter()
    changed = 0
    for i, h in enumerate(header):
        name = re.sub(r"\s+", " ", h.strip())
        if not name:
            name = f"colonna_{i + 1}"
        base = name
        used[base] += 1
        if used[base] > 1:
            name = f"{base}_{used[base]}"
        if name != h:
            changed += 1
        out.append(name)
    return out, changed


def fix_csv(text: str, *, max_rows_type_scan: int = 5000) -> dict[str, Any]:
    """Restituisce {content, changes, separatore_originale, righe, colonne}."""
    changes: list[dict[str, str]] = []

    bom = text.startswith(_BOM)
    if bom:
        text = text.lstrip(_BOM)
        changes.append({"codice": "bom", "messaggio": "Rimosso il BOM iniziale."})

    if not text.strip():
        return {"content": "", "changes": changes, "separatore_originale": None, "righe": 0, "colonne": 0}

    sample = "\n".join(text.splitlines()[:50])
    delimiter = _detect_delimiter(sample)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not rows:
        return {"content": "", "changes": changes, "separatore_originale": delimiter, "righe": 0, "colonne": 0}

    header_in = [h for h in rows[0]]
    body = rows[1:]
    n_cols = len(header_in)

    header_out, header_changed = _fix_headers(header_in)
    if header_changed:
        changes.append({"codice": "header", "messaggio": f"Intestazioni ripulite/uniformate: {header_changed}."})

    # tipo dominante per colonna (per le date) su un campione
    col_type: dict[int, str] = {}
    for i in range(n_cols):
        tipi = Counter(
            _cell_type(r[i]) for r in body[:max_rows_type_scan] if i < len(r) and not _is_empty(r[i])
        )
        col_type[i] = tipi.most_common(1)[0][0] if tipi else "vuoto"

    n_trim = n_date = n_dec = 0
    out_rows: list[list[str]] = [header_out]
    for r in body:
        new_r: list[str] = []
        for i, cell in enumerate(r):
            v = cell.strip()
            if v != cell:
                n_trim += 1
            if v and _RE_DEC_IT.match(v):  # decimale con virgola → punto (sempre sicuro)
                conv = _it_decimal_to_dot(v)
                if conv != v:
                    v = conv
                    n_dec += 1
            elif v and i < n_cols and col_type.get(i) == "data":  # date → ISO
                iso = _to_iso(v)
                if iso:
                    v = iso
                    n_date += 1
            new_r.append(v)
        out_rows.append(new_r)

    if n_trim:
        changes.append({"codice": "spazi", "messaggio": f"Rimossi spazi superflui in {n_trim} celle."})
    if n_date:
        changes.append({"codice": "date_iso", "messaggio": f"Convertite {n_date} date nel formato ISO aaaa-mm-gg."})
    if n_dec:
        changes.append({"codice": "decimali", "messaggio": f"Normalizzati {n_dec} numeri decimali (virgola → punto)."})
    if delimiter != ",":
        changes.append({"codice": "separatore", "messaggio": f"Separatore uniformato da «{delimiter}» a virgola (standard)."})

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=",", lineterminator="\n")
    writer.writerows(out_rows)

    return {
        "content": buf.getvalue(),
        "changes": changes,
        "separatore_originale": delimiter,
        "righe": len(body),
        "colonne": n_cols,
    }
