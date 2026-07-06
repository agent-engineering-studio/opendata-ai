"""Generatore di metadati schema.org/Dataset da un file profilato (Punto 04 #52).

`generate_schema_org(profile, ...)` è il gemello di `dcat.py::generate_dcat`
ma nel vocabolario **schema.org** (JSON-LD `Dataset`), usato da Google Dataset
Search e da molti portali oltre a DCAT-AP_IT. Stessa filosofia: deduce
DETERMINISTICAMENTE ciò che si misura dal file (formato, tipo di codifica,
variabili) e lascia come segnaposto i campi editoriali non deducibili (nome,
descrizione, licenza, editore) — mai inventati. Pure Python (nessun LLM).
"""

from __future__ import annotations

from typing import Any

from .dcat import _FORMAT_MEDIA, _XSD, _keywords_from_headers

_PLACEHOLDER = "<da compilare>"


def generate_schema_org(
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
    """Scheletro schema.org/Dataset + variabili + elenco campi da completare."""
    fmt = (profile.get("format") or "CSV").upper()
    _, media_type = _FORMAT_MEDIA.get(fmt, (fmt, "application/octet-stream"))

    variable_measured: list[str] = []
    schema_campi: list[dict[str, str]] = []
    headers: list[str] = []
    for col in profile.get("colonne_profilo") or []:
        nome = col.get("nome", "")
        headers.append(nome)
        if nome:
            variable_measured.append(nome)
            schema_campi.append({"nome": nome, "tipo_xsd": _XSD.get(col.get("tipo", "testo"), "xsd:string")})
    keyword = _keywords_from_headers(headers)

    distribution: dict[str, Any] = {
        "@type": "DataDownload",
        "encodingFormat": media_type,
        "contentUrl": url or "<URL del file>",
    }

    dataset: dict[str, Any] = {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": titolo or _PLACEHOLDER,
        "description": descrizione or _PLACEHOLDER,
        "identifier": _PLACEHOLDER,
        "keywords": keyword or [_PLACEHOLDER],
        "license": licenza or "<da compilare: es. CC-BY-4.0>",
        "creator": {"@type": "Organization", "name": ente or _PLACEHOLDER},
        "publisher": {"@type": "Organization", "name": ente or _PLACEHOLDER},
        "temporalCoverage": frequenza or "<da compilare: es. ANNUAL>",
        "distribution": [distribution],
    }
    if variable_measured:
        dataset["variableMeasured"] = variable_measured
    if tema:
        dataset["about"] = tema

    campi_mancanti: list[str] = []
    if not titolo:
        campi_mancanti.append("nome (name)")
    if not descrizione:
        campi_mancanti.append("descrizione (description)")
    if not licenza:
        campi_mancanti.append("licenza (license) — suggerita CC-BY-4.0")
    if not ente:
        campi_mancanti.append("editore (creator/publisher)")
    if not tema:
        campi_mancanti.append("argomento (about)")
    if not frequenza:
        campi_mancanti.append("copertura temporale/frequenza (temporalCoverage)")

    return {
        "profilo": "schema.org/Dataset",
        "dataset": dataset,
        "schema_campi": schema_campi,
        "campi_mancanti": campi_mancanti,
    }
