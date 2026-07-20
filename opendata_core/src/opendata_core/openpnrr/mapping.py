"""Costanti e helper per il client OpenPNRR (openpolis).

Fonte: API REST pubblica DRF su ``https://openpnrr.it/api/v1`` (nessuna auth
sulle liste). Licenza dati: **ODbL 1.0** (attribuzione richiesta) — ogni output
del connettore riporta ``licenza`` + ``source_url`` risolvibile.
"""

from __future__ import annotations

from typing import Any

#: Licenza dei dati OpenPNRR (Open Data Commons Open Database License 1.0).
LICENZA = "ODbL 1.0 (Open Data Commons Open Database License) — attribuzione: openpolis, openpnrr.it"

#: page_size massimo sensato per una singola pagina (protegge il budget di contesto).
MAX_PAGE_SIZE = 100

#: Filtri whitelisted per /progetti (gli altri sono ignorati silenziosamente da DRF).
PROGETTI_FILTERS = frozenset({
    "descrizione",
    "misura_codice_identificativo",
    "componente__codice_identificativo",
    "missione__codice_identificativo",
    "territori",
    "organizzazioni",
    "tema",
    "validato",
})

#: Filtri whitelisted per /misure.
MISURE_FILTERS = frozenset({
    "codice_misura",
    "componente__codice",
    "tipologia",
    "tipo_riforma",
    "tipo_investimento",
    "status",
    "territori",
})

#: Filtri whitelisted per /scadenze.
SCADENZE_FILTERS = frozenset({
    "misure__codice_identificativo",
    "status",
    "tempistica_completamento_anno",
    "tempistica_completamento_trimestre",
    "ita_ue",
})

#: Filtri whitelisted per /territori.
TERRITORI_FILTERS = frozenset({"denominazione", "istat_id", "opdm_id", "tipologia"})


def parse_amount(value: Any) -> float | None:
    """Converte un importo (str con virgola o punto decimale, o numero) in float.

    Gli importi OpenPNRR arrivano come stringhe (es. ``"3773260.36"``); alcuni
    campi potrebbero usare la virgola decimale all'italiana. Ritorna None per
    valori vuoti/non parsabili (fail-safe: mai sollevare sul parsing).
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    # Se ci sono sia '.' sia ',', assume '.' migliaia e ',' decimali (it).
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def id_from_url(url: str | None) -> int | None:
    """Estrae l'id numerico dall'ultimo segmento di un URL API (o None)."""
    if not url:
        return None
    tail = str(url).rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None
