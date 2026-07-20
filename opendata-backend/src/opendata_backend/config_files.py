"""Loader dei file di configurazione YAML del backend (Fase 0).

I YAML vivono IN-PACKAGE sotto `config_data/` così da essere impacchettati col
wheel e disponibili ovunque il pacchetto sia installato (dev e container), senza
modifiche al Dockerfile. La directory non si chiama `config/` per non collidere
col modulo `config.py` (Settings). Override del percorso via `OPENDATA_CONFIG_DIR`.

Caricamento cache-ato (`lru_cache`): i pesi/tassonomia cambiano solo a deploy.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_DIR = Path(__file__).parent / "config_data"


def _config_dir() -> Path:
    override = os.getenv("OPENDATA_CONFIG_DIR")
    return Path(override) if override else _DEFAULT_DIR


def _load_yaml(name: str) -> dict[str, Any]:
    path = _config_dir() / name
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Config {name!r}: atteso un mapping YAML, trovato {type(data).__name__}")
    return data


@lru_cache(maxsize=None)
def maturity_weights() -> dict[str, Any]:
    """Pesi per dimensione + soglie di livello (maturity_weights.yaml)."""
    return _load_yaml("maturity_weights.yaml")


@lru_cache(maxsize=None)
def value_taxonomy() -> dict[str, Any]:
    """Tassonomia di valore (value_taxonomy.yaml)."""
    return _load_yaml("value_taxonomy.yaml")


@lru_cache(maxsize=None)
def civic_kpi() -> dict[str, Any]:
    """KPI civici versionati (civic_kpi.yaml)."""
    return _load_yaml("civic_kpi.yaml")


@lru_cache(maxsize=None)
def portali_regionali() -> dict[str, Any]:
    """Registro portali CKAN regionali per il fallback maturità (portali_regionali.yaml)."""
    return _load_yaml("portali_regionali.yaml")


@lru_cache(maxsize=None)
def regioni() -> dict[str, Any]:
    """Registro regioni ISTAT → scoping mono-regione (regioni.yaml).

    Ritorna il mapping `cod_regione` (str 2 cifre) → config regione, da cui la
    derivazione in `config.py` (province, portale CKAN, OpenCoesione, fq) parte
    quando `REGION` è impostato. Vedi `region_config`/`province_scope`.
    """
    data = _load_yaml("regioni.yaml")
    regs = data.get("regioni")
    return regs if isinstance(regs, dict) else {}


@lru_cache(maxsize=None)
def maturity_coverage() -> dict[str, Any]:
    """Template collection ottimale per tipo di ente (maturity_coverage.yaml)."""
    return _load_yaml("maturity_coverage.yaml")


@lru_cache(maxsize=None)
def rigenerazione_patterns() -> list[dict[str, Any]]:
    """Catalogo dei pattern di rigenerazione (rigenerazione_patterns.yaml).

    Ritorna la lista `patterns` da iniettare nel motore puro
    `opendata_core.rigenerazione.valuta_pattern`.
    """
    data = _load_yaml("rigenerazione_patterns.yaml")
    pats = data.get("patterns")
    return pats if isinstance(pats, list) else []


__all__ = [
    "maturity_weights",
    "value_taxonomy",
    "civic_kpi",
    "portali_regionali",
    "regioni",
    "maturity_coverage",
    "rigenerazione_patterns",
]
