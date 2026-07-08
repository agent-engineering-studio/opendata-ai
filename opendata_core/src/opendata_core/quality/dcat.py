"""Generatore di metadati DCAT-AP_IT da un file profilato (Data Quality Lab #49).

`generate_dcat(profile, ...)` costruisce lo scheletro di una scheda **DCAT-AP_IT**
(Dataset + Distribution) pronta da incollare su un portale CKAN: ricava in modo
DETERMINISTICO ciò che si misura dal file (formato, media type, schema dei campi
con tipi XSD, n. record, keyword dai nomi colonna) e lascia come segnaposto
`<da compilare>` i campi editoriali che NON si possono dedurre (titolo,
descrizione, licenza, ente, tema, frequenza) — mai inventati. `campi_mancanti`
elenca cosa resta da completare. Pure Python (nessun LLM).
"""

from __future__ import annotations

import re
from typing import Any

from .hvd import advise_hvd

_PLACEHOLDER = "<da compilare>"

# Profilo OpenData AI (tipo colonna) → tipo XSD per lo schema dei campi.
_XSD = {
    "intero": "xsd:integer",
    "decimale": "xsd:decimal",
    "percentuale": "xsd:decimal",
    "data": "xsd:date",
    "booleano": "xsd:boolean",
    "testo": "xsd:string",
    "vuoto": "xsd:string",
}

# Formato file → (etichetta DCT format, IANA media type).
_FORMAT_MEDIA = {
    "CSV": ("CSV", "text/csv"),
    "TSV": ("TSV", "text/tab-separated-values"),
    "TXT": ("CSV", "text/csv"),
    "GEOJSON": ("GEOJSON", "application/geo+json"),
    "JSON": ("JSON", "application/json"),
}

# Licenze aperte comuni → suggerimento (mostrato all'utente, non imposto).
_STOP_KW = {
    "id", "cod", "codice", "anno", "data", "valore", "valori", "nome", "n",
    "the", "geom", "geometry", "fid", "objectid", "x", "y", "lat", "lon",
}


def _keywords_from_headers(headers: list[str], limit: int = 8) -> list[str]:
    """Keyword candidate dai nomi colonna: token alfabetici, puliti e dedotti."""
    out: list[str] = []
    seen: set[str] = set()
    for h in headers:
        for tok in re.split(r"[^0-9A-Za-zàèéìòùÀÈÉÌÒÙ]+", (h or "").lower()):
            if len(tok) < 3 or tok in _STOP_KW or tok.isdigit() or tok in seen:
                continue
            seen.add(tok)
            out.append(tok)
            if len(out) >= limit:
                return out
    return out


def generate_dcat(
    profile: dict[str, Any],
    *,
    titolo: str | None = None,
    descrizione: str | None = None,
    licenza: str | None = None,
    ente: str | None = None,
    tema: str | None = None,
    frequenza: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Scheletro DCAT-AP_IT + schema campi + elenco campi da completare."""
    fmt = (profile.get("format") or "CSV").upper()
    dct_format, media_type = _FORMAT_MEDIA.get(fmt, (fmt, "application/octet-stream"))

    # ── schema dei campi + keyword (solo per i tabellari, dal profilo colonne) ──
    schema_campi: list[dict[str, str]] = []
    headers: list[str] = []
    for col in profile.get("colonne_profilo") or []:
        nome = col.get("nome", "")
        headers.append(nome)
        schema_campi.append({"nome": nome, "tipo_xsd": _XSD.get(col.get("tipo", "testo"), "xsd:string")})
    keyword = _keywords_from_headers(headers)

    distribution: dict[str, Any] = {
        "@type": "dcat:Distribution",
        "dct:format": dct_format,
        "dcat:mediaType": media_type,
        "dcat:downloadURL": url or "<URL del file>",
        "dct:license": licenza or _PLACEHOLDER,
    }

    dataset: dict[str, Any] = {
        "@type": "dcat:Dataset",
        "dct:title": titolo or _PLACEHOLDER,
        "dct:description": descrizione or _PLACEHOLDER,
        "dct:identifier": _PLACEHOLDER,
        "dcat:keyword": keyword or [_PLACEHOLDER],
        "dcat:theme": tema or "<da compilare: tema EU, es. GOVE/ECON/ENVI>",
        "dct:publisher": {"@type": "foaf:Agent", "foaf:name": ente or _PLACEHOLDER},
        "dct:accrualPeriodicity": frequenza or "<da compilare: es. ANNUAL>",
        "dct:license": licenza or "<da compilare: es. CC-BY-4.0>",
        "dcat:distribution": [distribution],
    }

    # campi obbligatori DCAT-AP_IT non deducibili dal file → da completare a mano
    campi_mancanti: list[str] = []
    if not titolo:
        campi_mancanti.append("titolo (dct:title)")
    if not descrizione:
        campi_mancanti.append("descrizione (dct:description)")
    if not licenza:
        campi_mancanti.append("licenza (dct:license) — suggerita CC-BY-4.0")
    if not ente:
        campi_mancanti.append("ente titolare (dct:publisher)")
    if not tema:
        campi_mancanti.append("tema EU (dcat:theme)")
    if not frequenza:
        campi_mancanti.append("frequenza di aggiornamento (dct:accrualPeriodicity)")

    # stima HVD (#102): informativa, con confidenza — mai compilata in dcat:theme
    hvd = advise_hvd(profile, titolo=titolo, url=url)

    return {
        "profilo": "DCAT-AP_IT",
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
            "foaf": "http://xmlns.com/foaf/0.1/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
        },
        "dataset": dataset,
        "schema_campi": schema_campi,
        "campi_mancanti": campi_mancanti,
        "hvd_stimata": hvd["categorie"][0] if hvd["categorie"] else None,
    }
