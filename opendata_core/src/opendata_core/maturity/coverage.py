"""Analisi di copertura tematica/settoriale (Fase A) — pura e deterministica.

Risponde alla domanda "quali contesti e settori coprire per una collection
ottimale": classifica ogni dataset in un settore (vocabolario temi DCAT-AP_IT),
confronta i settori coperti con la **collection ottimale attesa per il tipo di
ente** (template iniettabile) e segnala i settori core mancanti, ordinati per
priorità. Aggiunge la copertura delle 6 categorie HVD (Reg. UE 2023/138).

Niente HTTP/LLM/DB: il template è iniettato dal chiamante (default in models.py).
"""

from __future__ import annotations

import re

from .hvd import match_hvd_category
from .models import (
    DEFAULT_COVERAGE_TEMPLATES,
    DEFAULT_ENTITY_TYPE,
    SECTOR_LABELS,
    CoverageResult,
    DatasetInput,
    SectorCoverage,
)

# ── Classificazione in settori DCAT-AP_IT ────────────────────────────
#
# Codici tema DCAT-AP_IT riconosciuti nel campo `theme` (match diretto, ha
# precedenza sulle keyword). I codici regionali/locali (es. "POP") vengono
# ricondotti al settore via mappa sotto.
_DCAT_THEME_TO_SECTOR: dict[str, str] = {
    "agri": "AGRI", "econ": "ECON", "educ": "EDUC", "envi": "ENVI",
    "ener": "ENER", "heal": "HEAL", "gove": "GOVE", "just": "JUST",
    "regi": "REGI", "soci": "SOCI", "tech": "TECH", "tran": "TRAN",
    "intr": "INTR",
    # alias di codici/temi locali frequenti sui portali italiani
    "pop": "SOCI", "popolazione": "SOCI", "trasporti": "TRAN",
    "ambiente": "ENVI", "salute": "HEAL", "sanità": "HEAL",
    "economia": "ECON", "istruzione": "EDUC", "cultura": "EDUC",
    "energia": "ENER", "agricoltura": "AGRI", "territorio": "REGI",
}

# Keyword IT+EN per settore (fallback quando `theme` manca o non è un codice
# noto). Ordine = priorità in caso di match multipli. Match a confine di parola
# come prefisso (\bkw), coerente con hvd.py.
SECTOR_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("HEAL", (
        "salute", "sanit", "ospedal", "farmaci", "asl", "medic", "vaccin",
        "ricover", "health", "pronto soccorso", "consultor",
    )),
    ("TRAN", (
        "trasport", "mobilità", "mobility", "traffico", "gtfs", "fermate",
        "orari", "parcheggi", "piste ciclabili", "tpl", "autobus", "treni",
        "strad", "viabilità", "porti", "aeroport",
    )),
    ("ENVI", (
        "ambient", "rifiut", "raccolta differenziata", "qualità dell'aria",
        "inquinament", "acqua", "suolo", "biodiversità", "verde pubblico",
        "emission", "environment", "dissesto", "idrogeolog",
    )),
    ("ENER", (
        "energia", "energetic", "fotovoltaic", "rinnovabil", "gas", "elettric",
        "teleriscaldament", "consumi energetici", "energy",
    )),
    ("AGRI", (
        "agricol", "agro", "pesca", "silvicoltur", "alimentar", "zootecn",
        "vitivinicol", "agriculture", "food", "fishery",
    )),
    ("EDUC", (
        "scuol", "istruzione", "student", "universit", "formazione", "cultur",
        "biblioteche", "musei", "sport", "education", "school",
    )),
    ("ECON", (
        "bilancio", "tribut", "imu", "tari", "tasi", "tassa", "imposta",
        "spes", "entrat", "appalt", "contratti", "impres", "commercio",
        "attività produttive", "economia", "finanz", "pagamenti", "fattur",
    )),
    ("SOCI", (
        "popolazione", "demograf", "censiment", "residenti", "anagraf",
        "welfare", "sociale", "famiglie", "natalità", "stranier", "occupazion",
        "reddito", "society", "population",
    )),
    ("REGI", (
        "urbanistic", "territori", "catasto", "edilizia", "piano regolatore",
        "pgt", "puc", "zone", "quartier", "geospatial", "cartograf", "confini",
        "civici", "toponom", "particelle",
    )),
    ("JUST", (
        "sicurezza", "polizia local", "vigili", "ordinanze", "contravvenzion",
        "sanzioni", "giustizia", "legalità", "videosorveglianza",
    )),
    ("GOVE", (
        "delibere", "determine", "atti", "albo pretorio", "amministrazione",
        "trasparenza", "consiglio comunale", "giunta", "organigramma",
        "personale", "uffici", "procedimenti", "pubblica amministrazione",
        "elezioni", "sedute",
    )),
    ("TECH", (
        "ricerca", "innovazione", "brevett", "tecnolog", "digitale", "banda larga",
        "research", "technology",
    )),
]

# Etichette leggibili delle 6 categorie HVD (Reg. UE 2023/138).
HVD_LABELS: dict[str, str] = {
    "geospatial": "Geospaziale",
    "earth_observation_environment": "Osservazione della Terra e ambiente",
    "meteorological": "Meteorologici",
    "statistics": "Statistici",
    "companies_ownership": "Imprese e proprietà",
    "mobility": "Mobilità",
}
HVD_ALL: tuple[str, ...] = tuple(HVD_LABELS.keys())


def _matches(blob: str, kw: str) -> bool:
    return re.search(r"\b" + re.escape(kw), blob) is not None


def classify_sector(ds: DatasetInput) -> str | None:
    """Settore DCAT-AP_IT del dataset. `theme` (codice noto) ha precedenza,
    poi euristica keyword su titolo/descrizione/tag/theme. None se non classificabile."""
    if ds.theme:
        for token in re.split(r"[\s,;/|]+", ds.theme.strip().lower()):
            sec = _DCAT_THEME_TO_SECTOR.get(token)
            if sec:
                return sec
    blob = ds.keyword_blob
    for sector, keywords in SECTOR_KEYWORDS:
        if any(_matches(blob, kw) for kw in keywords):
            return sector
    return None


def infer_entity_type(name: str | None, *, has_istat: bool = False) -> str:
    """Inferisce il tipo di ente dal nome (e dalla presenza di un codice ISTAT).

    Il codice ISTAT identifica un comune. Altrimenti si guarda il prefisso
    istituzionale nel nome. Fallback: "ente" (template trasversale di base).
    """
    if has_istat:
        return "comune"
    n = (name or "").strip().lower()
    if n.startswith("comune"):
        return "comune"
    if n.startswith("regione"):
        return "regione"
    if n.startswith(("provincia", "città metropolitana", "citta metropolitana")):
        return "provincia"
    return DEFAULT_ENTITY_TYPE


def coverage_template(
    entity_type: str | None, templates: dict[str, dict[str, int]] | None = None
) -> dict[str, int]:
    """Template (settore → priorità) per il tipo di ente, con fallback su 'ente'."""
    tbl = templates or DEFAULT_COVERAGE_TEMPLATES
    et = (entity_type or DEFAULT_ENTITY_TYPE).strip().lower()
    return tbl.get(et) or tbl.get(DEFAULT_ENTITY_TYPE) or {}


def assess_coverage(
    datasets: list[DatasetInput],
    *,
    entity_type: str | None = None,
    templates: dict[str, dict[str, int]] | None = None,
) -> CoverageResult:
    """Valuta la copertura tematica di un ente rispetto alla collection ottimale.

    - classifica ogni dataset in un settore DCAT-AP_IT;
    - confronta i settori coperti con il template (core) del tipo di ente;
    - `coverage_score` = quota di settori core coperti (0–100);
    - `missing_core` = settori core senza dataset, ordinati per priorità;
    - copertura HVD = quali delle 6 categorie sono presenti/assenti.
    """
    et = (entity_type or DEFAULT_ENTITY_TYPE).strip().lower()
    template = coverage_template(et, templates)
    n_total = len(datasets)

    counts: dict[str, int] = {}
    hvd_seen: set[str] = set()
    n_unclassified = 0
    for ds in datasets:
        sec = classify_sector(ds)
        if sec is None:
            n_unclassified += 1
        else:
            counts[sec] = counts.get(sec, 0) + 1
        hvd = match_hvd_category(ds)
        if hvd:
            hvd_seen.add(hvd)

    # Unione di tutti i settori: quelli del template + quelli effettivamente visti.
    all_codes = sorted(set(template) | set(counts) | set(SECTOR_LABELS),
                       key=lambda c: (c not in template, template.get(c, 99), c))
    sectors: list[SectorCoverage] = []
    for code in all_codes:
        n = counts.get(code, 0)
        sectors.append(SectorCoverage(
            code=code,
            label=SECTOR_LABELS.get(code, code),
            n_datasets=n,
            share=(n / n_total) if n_total else 0.0,
            is_core=code in template,
            present=n > 0,
            priority=template.get(code),
        ))

    core_codes = list(template)
    covered_core = [c for c in core_codes if counts.get(c, 0) > 0]
    coverage_score = round(len(covered_core) / len(core_codes) * 100, 1) if core_codes else 0.0
    missing_core = tuple(
        s for s in sorted(
            (sc for sc in sectors if sc.is_core and not sc.present),
            key=lambda sc: sc.priority or 99,
        )
    )

    hvd_present = tuple(h for h in HVD_ALL if h in hvd_seen)
    hvd_missing = tuple(h for h in HVD_ALL if h not in hvd_seen)

    return CoverageResult(
        entity_type=et,
        sectors=tuple(sectors),
        missing_core=missing_core,
        hvd_present=hvd_present,
        hvd_missing=hvd_missing,
        coverage_score=coverage_score,
        n_classified=n_total - n_unclassified,
        n_unclassified=n_unclassified,
    )
