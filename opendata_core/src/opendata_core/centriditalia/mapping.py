"""Costanti e schema del mirror per il connettore Centri d'Italia (openpolis).

Fonte: file **bulk** CSV su S3 elencati su https://centriditalia.it/pages/open-data
(NON un'API REST). Licenza dati: **CC-BY 4.0** — attribuzione: openpolis /
Centri d'Italia. Ogni output del connettore riporta ``licenza`` + ``source_url``
(il CSV originale) + la data di refresh del mirror.

I codici ``*_codice_istat`` mappano 1:1 sui codici ISTAT usati nel resto della
piattaforma (stesso pattern di OpenPNRR/OpenCoesione).

Il dizionario delle colonne è pubblicato in ``metadati_centri_v2026.xlsx`` (vedi
README): le descrizioni NON vanno inventate.
"""

from __future__ import annotations

import os

#: Licenza dei dati Centri d'Italia.
LICENZA = "CC-BY 4.0 — attribuzione: openpolis / Centri d'Italia (centriditalia.it)"

#: Base S3 dei file open data (override via env per test/mirror alternativi).
S3_BASE = os.getenv(
    "CENTRIDITALIA_BASE_URL",
    "https://migrantidb.s3.eu-central-1.amazonaws.com/opendata",
)

#: Tag di versione nei nomi file (i file sono versionati per anno, es. _v2026).
VERSION = os.getenv("CENTRIDITALIA_DATASET_VERSION", "v2026")

#: URL del dizionario colonne (citato nel README, non scaricato dal client).
METADATI_URL = f"{S3_BASE}/metadati_centri_{VERSION}.xlsx"

#: NB: bandi_ANAC_accoglienza_*.csv è ESCLUSO — risponde AccessDenied (403) su S3
#: (verificato). Reintrodurre solo se/quando l'URL torna pubblico.

# Tipi colonna per il mirror SQLite: INTEGER/REAL per gli aggregabili, TEXT resto.
_INT = "INTEGER"
_REAL = "REAL"


def _csv_url(stem: str) -> str:
    return f"{S3_BASE}/{stem}_{VERSION}.csv"


#: Definizione dei dataset del mirror: nome logico → (url, tabella, colonne
#: whitelisted con tipo). Si caricano SOLO queste colonne (per nome header),
#: ignorando eventuali colonne extra → robusto ai cambi di schema minori.
DATASETS: dict[str, dict] = {
    "centri": {
        "url": _csv_url("centri_cas_cpa_hotspot"),
        "table": "centri",
        "columns": {
            "rilevazione_data": "TEXT",
            "centro_id": "TEXT",
            "centro_denominazione": "TEXT",
            "comune_denominazione": "TEXT",
            "comune_codice_istat": "TEXT",
            "provincia_cm_denominazione": "TEXT",
            "provincia_cm_codice_istat": "TEXT",
            "provincia_cm_sigla": "TEXT",
            "regione_denominazione": "TEXT",
            "regione_codice_istat": "TEXT",
            "ente_gestore": "TEXT",
            "data_stipula_convenzione": "TEXT",
            "data_scadenza_convenzione": "TEXT",
            "data_scadenza_proroga": "TEXT",
            "costo_giornaliero_per_ospite": _REAL,
            "presenze_giornaliere": _INT,
            "capienza": _INT,
            "procedura_affidamento": "TEXT",
            "operativita": "TEXT",
            "tipologia_centro": "TEXT",
            "tipologia_ospiti": "TEXT",
        },
    },
    "sai_progetti": {
        "url": _csv_url("sai_progetti"),
        "table": "sai_progetti",
        "columns": {
            "progetto_codice": "TEXT",
            "data_riferimento": "TEXT",
            "ente_locale_progetto": "TEXT",
            "tipologia": "TEXT",
            "capienza": _INT,
            "presenze": _INT,
            "comune_denominazione": "TEXT",
            "comune_codice_istat": "TEXT",
            "provincia_cm_codice_istat": "TEXT",
            "provincia_cm_sigla": "TEXT",
            "regione_denominazione": "TEXT",
            "regione_codice_istat": "TEXT",
        },
    },
    "sai_strutture": {
        "url": _csv_url("sai_struttura"),
        "table": "sai_strutture",
        "columns": {
            "sai_struttura_id": "TEXT",
            "sai_struttura_denominazione": "TEXT",
            "comune_denominazione": "TEXT",
            "comune_codice_istat": "TEXT",
            "provincia_cm_codice_istat": "TEXT",
            "regione_codice_istat": "TEXT",
            "sai_struttura_tipologia": "TEXT",
            "sai_progetto_codice": "TEXT",
            "sai_progetto_denominazione": "TEXT",
            "data_inizio": "TEXT",
            "data_fine": "TEXT",
            "data_rilevazione": "TEXT",
            "capienza": _INT,
            "presenze_giornaliere": _INT,
        },
    },
}


def source_url(dataset: str) -> str:
    """URL del CSV originale di un dataset (per il blocco `sources`)."""
    return DATASETS[dataset]["url"]


def parse_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", ".")))
    except (ValueError, TypeError):
        return None


def parse_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    s = str(value).strip()
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def norm_istat(code: str | int | None, width: int) -> str | None:
    """Normalizza un codice ISTAT a larghezza fissa con zero-padding (comune=6)."""
    if code is None:
        return None
    s = str(code).strip()
    return s.zfill(width) if s.isdigit() else s or None
