"""Consigli di scala/performance da un profilo CSV (Punto 03 #51, "Veloce anche
quando è grande").

`advise_scale(profile, *, size_bytes)` legge il profilo di `profile_csv` (righe,
colonne, tipi, cardinalità) e suggerisce, in modo deterministico e condizionato a
ciò che si misura, come rendere il dato veloce da consultare anche quando è grande:
formato colonnare (Parquet), indici, partizionamento e modalità di esposizione.
Niente LLM, niente dipendenze.
"""

from __future__ import annotations

from typing import Any

from .schema import _RE_KEY_NAME

# soglie (per righe; la dimensione in byte rafforza la classe)
_BIG_ROWS = 100_000
_MED_ROWS = 10_000
_BIG_BYTES = 50 * 1024 * 1024
_MED_BYTES = 5 * 1024 * 1024
_MAX_CAT_DISTINCT = 50  # colonna categoriale "utile" come chiave/partizione


def _human_size(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024 or unit == "GB":
            return f"{f:.0f} {unit}" if unit == "B" else f"{f:.1f} {unit}"
        f /= 1024
    return f"{f:.1f} GB"


def _consiglio(codice: str, titolo: str, dettaglio: str, priorita: str) -> dict[str, str]:
    return {"codice": codice, "titolo": titolo, "dettaglio": dettaglio, "priorita": priorita}


def advise_scale(profile: dict[str, Any], *, size_bytes: int | None = None) -> dict[str, Any]:
    """Consigli di scala/performance dal profilo di un CSV."""
    cols = profile.get("colonne_profilo") or []
    n_rows = int(profile.get("righe") or 0)
    n_cols = int(profile.get("colonne") or len(cols))

    # stima dimensione: byte reali se noti, altrimenti ~12 byte/cella
    estimated = size_bytes is None
    eff_bytes = size_bytes if size_bytes is not None else n_rows * max(n_cols, 1) * 12

    if n_rows >= _BIG_ROWS or eff_bytes >= _BIG_BYTES:
        classe = "grande"
    elif n_rows >= _MED_ROWS or eff_bytes >= _MED_BYTES:
        classe = "medio"
    else:
        classe = "piccolo"

    # colonne utili per indici/partizioni
    date_cols = [c["nome"] for c in cols if c.get("tipo") == "data"]
    key_cols = [c["nome"] for c in cols if _RE_KEY_NAME.search(str(c.get("nome", "")))]
    cat_cols = [
        c["nome"] for c in cols
        if c.get("tipo") in ("testo", "booleano") and 2 <= int(c.get("distinti") or 0) <= _MAX_CAT_DISTINCT
    ]
    # testo ad alta cardinalità ma ripetuto (candidato a dictionary/lookup)
    repeated_text = [
        c["nome"] for c in cols
        if c.get("tipo") == "testo"
        and n_rows
        and _MAX_CAT_DISTINCT < int(c.get("distinti") or 0) <= n_rows * 0.5
    ]

    consigli: list[dict[str, str]] = []

    if classe in ("medio", "grande"):
        consigli.append(_consiglio(
            "parquet",
            "Affianca un formato colonnare (Parquet)",
            "Pubblica anche una versione Parquet: compressa (file fino a ~70% più piccolo) e "
            "molto più veloce per le query analitiche, che leggono solo le colonne servite. "
            "Tieni il CSV per la massima interoperabilità.",
            "alta" if classe == "grande" else "media",
        ))

    if classe == "grande":
        if date_cols:
            consigli.append(_consiglio(
                "partizione_tempo",
                f"Partiziona per periodo (colonna «{date_cols[0]}»)",
                "Suddividi per anno: le query su un intervallo temporale leggono solo le "
                "partizioni utili invece dell'intero dataset.",
                "media",
            ))
        elif cat_cols:
            consigli.append(_consiglio(
                "partizione_categoria",
                f"Partiziona per categoria (colonna «{cat_cols[0]}»)",
                "Suddividi i dati per questa colonna a bassa cardinalità: chi ne consulta una "
                "parte non scarica tutto.",
                "media",
            ))
        else:
            consigli.append(_consiglio(
                "partizione",
                "Valuta il partizionamento",
                "Per dataset così grandi, suddividere i file (per periodo o categoria) evita "
                "download e scansioni dell'intero contenuto.",
                "bassa",
            ))

    index_cols = list(dict.fromkeys(date_cols + key_cols + cat_cols))
    if classe in ("medio", "grande") and index_cols:
        consigli.append(_consiglio(
            "indici",
            "Indicizza le colonne di filtro/join",
            "Se carichi il dato in un database, crea indici su: "
            + ", ".join(f"«{c}»" for c in index_cols[:6])
            + " — sono le colonne tipiche di filtro, ricerca e join.",
            "media",
        ))

    if classe in ("medio", "grande") and repeated_text:
        consigli.append(_consiglio(
            "lookup",
            "Normalizza il testo ripetuto",
            "Colonne come "
            + ", ".join(f"«{c}»" for c in repeated_text[:4])
            + " ripetono molti valori uguali: spostarle in una tabella di lookup (codice → "
            "descrizione) riduce dimensione e incoerenze.",
            "bassa",
        ))

    if classe == "grande":
        consigli.append(_consiglio(
            "esposizione",
            "Esponi via API/DataStore con paginazione",
            "Invece di un unico download da centinaia di MB, offri un endpoint paginato/"
            "filtrabile (es. CKAN DataStore): l'utente preleva solo ciò che gli serve.",
            "media",
        ))

    if not consigli:
        consigli.append(_consiglio(
            "ok",
            "Nessun accorgimento particolare",
            "Il dataset è piccolo: il CSV va benissimo così, senza formati o partizionamenti "
            "speciali.",
            "bassa",
        ))

    return {
        "righe": n_rows,
        "colonne": n_cols,
        "dimensione": {
            "bytes": eff_bytes,
            "leggibile": _human_size(eff_bytes),
            "stimata": estimated,
            "classe": classe,
        },
        "consigli": consigli,
    }
