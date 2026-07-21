"""Loader del catalogo dei dataset candidati (#172, D1 di #170).

Motore **puro**: nessun LLM, nessun I/O di rete. Carica il catalogo YAML
impacchettato nel wheel (`catalog_data.yaml`) via ``importlib.resources`` e lo
valida in `CandidateDataset`. Cache-ato (`lru_cache`): il catalogo cambia solo a
deploy. Percorso override via env ``DATAPLAN_CATALOG_PATH`` (test / cataloghi
regionali alternativi).
"""

from __future__ import annotations

import os
from functools import lru_cache
from importlib import resources
from pathlib import Path

import yaml

from .models import CandidateDataset

_RESOURCE = "catalog_data.yaml"


def _raw() -> dict:
    override = os.getenv("DATAPLAN_CATALOG_PATH")
    if override:
        text = Path(override).read_text(encoding="utf-8")
    else:
        text = resources.files(__package__).joinpath(_RESOURCE).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Catalogo dataplan: atteso un mapping YAML, trovato {type(data).__name__}")
    return data


@lru_cache(maxsize=None)
def load_catalog() -> tuple[CandidateDataset, ...]:
    """Il catalogo dei dataset candidati (tuple immutabile, cache-ata).

    Solleva ValueError su id duplicati o voci non valide (fail-fast a deploy).
    """
    raw = _raw()
    voci = raw.get("candidati") or []
    if not isinstance(voci, list):
        raise ValueError("Catalogo dataplan: 'candidati' deve essere una lista.")
    out = [CandidateDataset(**v) for v in voci]
    ids = [c.id for c in out]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Catalogo dataplan: id duplicati: {', '.join(sorted(dupes))}")
    return tuple(out)


def catalog_by_area() -> dict[str, list[CandidateDataset]]:
    """Candidati raggruppati per area (Tributi, SIT, Ambiente, …)."""
    grouped: dict[str, list[CandidateDataset]] = {}
    for c in load_catalog():
        grouped.setdefault(c.area, []).append(c)
    return grouped


def clear_cache() -> None:
    """Invalida la cache del catalogo (utile nei test con override)."""
    load_catalog.cache_clear()
