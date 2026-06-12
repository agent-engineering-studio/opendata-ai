"""Real-world mapping of the OpenCoesione API, written during discovery (2026-06-12).

Everything in this module was verified against the live API at
https://opencoesione.gov.it/it/api — do NOT extend the filter whitelists without
re-probing: the server silently ignores unknown query parameters (e.g.
``cod_comune=072006`` on /progetti returns the FULL unfiltered count), so a typo
becomes a wrong-but-plausible answer instead of an error.

Verified behaviours:
  - API root (``/it/api/``) is plain JSON listing the resources:
    progetti, soggetti, aggregati, temi, nature, territori, programmi,
    plus ``data_aggiornamento`` (YYYYMMDD).
  - JSON via ``.json`` suffix; list endpoints paginate with
    ``page``/``page_size`` (page_size is server-capped at 500) and return
    count/next/previous/current_page/last_page/facet_counts/results.
  - /progetti filters: territorio (slug, e.g. "bari-comune"), tema (slug),
    natura (slug), stato, ciclo_programmazione (e.g. "2014_2020"), fonte, focus.
  - /soggetti filters: territorio, tema, natura, ruolo. ``denominazione`` is
    NOT supported (silently ignored).
  - /territori filters: tipo (C|P|R|E), denominazione, cod_reg, cod_prov,
    cod_com (integers — ISTAT codes without leading zeros: "072006" → 72006).
    8052 rows total, ~7900 comuni.
  - /aggregati/territori/{slug}.json: contesto (popolazione!), totali
    (costo_pubblico, pagamenti, progetti), stati_progetti, temi, nature,
    impegni_e_pagamenti_per_anno. Accepts ``ciclo_programmazione`` as filter.
  - Detail at /progetti/{clp-lowercase}/ — amounts use Italian decimal commas
    ("4363566537,13"), dates are YYYYMMDD, ``percentuale_avanzamento`` is "100%".
  - Throttling: HTTP 429 after a couple of rapid requests, JSON body
    ``{"detail": "… Expected available in N second(s)."}``.

Licence: API data CC BY-SA 3.0; bulk datasets CC BY 4.0. Cite in every output.
"""

from __future__ import annotations

from datetime import date

# ──────────────────────────── filter whitelists ────────────────────────────
# The server silently ignores unknown params — only ship what was verified.

PROGETTI_FILTERS = frozenset(
    {"territorio", "tema", "natura", "stato", "ciclo_programmazione", "fonte", "focus"}
)
SOGGETTI_FILTERS = frozenset({"territorio", "tema", "natura", "ruolo"})
TERRITORI_FILTERS = frozenset({"tipo", "denominazione", "cod_reg", "cod_prov", "cod_com"})
AGGREGATI_FILTERS = frozenset({"ciclo_programmazione"})

# ─────────────────────────────── enumerations ──────────────────────────────

#: Programming cycles as the API spells them (facet ``ciclo_programmazione``).
CICLI = ("2000_2006", "2007_2013", "2014_2020", "2021_2027")

#: Synthetic theme slugs (the 11 entries of /temi, also used as facet values).
TEMI = (
    "ricerca-e-innovazione",
    "reti-servizi-digitali",
    "competitivita-imprese",
    "energia",
    "ambiente",
    "cultura-e-turismo",
    "trasporti",
    "occupazione",
    "inclusione-sociale",
    "istruzione",
    "capacita-amministrativa",
)

#: Project nature slugs (the 6 entries of /nature).
NATURE = (
    "acquisto-beni-e-servizi",
    "infrastrutture",
    "incentivi-alle-imprese",
    "contributi-a-persone",
    "conferimenti-capitale",
    "non-disponibile",
)

#: Project state facet values, in lifecycle order.
STATI = ("non_determinabile", "non_avviato", "in_corso", "liquidato", "concluso")

#: States counted as "completed" by funding-capacity computations.
STATI_CONCLUSI = ("liquidato", "concluso")

#: Territory types accepted by /territori (C=comune, P=provincia, R=regione, E=estero).
TIPI_TERRITORIO = ("C", "P", "R", "E")

LICENZA_API = "Dati API OpenCoesione — CC BY-SA 3.0"
LICENZA_BULK = "Dataset bulk OpenCoesione — CC BY 4.0"


# ───────────────────────────── value normalisers ───────────────────────────


def normalize_ciclo(value: str) -> str:
    """Accept ``2014-2020`` / ``2014_2020`` / ``2014 2020`` and return the API form.

    Raises ValueError with the valid options when the cycle does not exist.
    """
    norm = value.strip().replace("-", "_").replace(" ", "_")
    if norm not in CICLI:
        raise ValueError(f"Ciclo {value!r} non valido. Valori ammessi: {', '.join(CICLI)}")
    return norm


def normalize_slug_value(value: str, allowed: tuple[str, ...], what: str) -> str:
    """Validate a slug-valued filter against the discovery enumeration."""
    norm = value.strip().lower().replace(" ", "-").replace("_", "-")
    if norm not in allowed:
        raise ValueError(f"{what} {value!r} non valido. Valori ammessi: {', '.join(allowed)}")
    return norm


def comune_code_int(cod_comune: str | int) -> int:
    """ISTAT comune code → the integer form used by /territori (``"072006"`` → 72006)."""
    try:
        return int(str(cod_comune).strip())
    except ValueError as exc:
        raise ValueError(
            f"Codice comune ISTAT {cod_comune!r} non valido: atteso numerico (es. '072006')."
        ) from exc


def parse_amount(value: str | float | int | None) -> float | None:
    """Parse an Italian-formatted money string (``"4363566537,13"``) into a float."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = value.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_yyyymmdd(value: str | None) -> date | None:
    """Parse the API ``YYYYMMDD`` date format; empty strings become None."""
    raw = (value or "").strip()
    if len(raw) != 8 or not raw.isdigit():
        return None
    try:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    except ValueError:
        return None
