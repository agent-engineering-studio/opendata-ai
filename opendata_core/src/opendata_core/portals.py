"""Registro dei portali CKAN regionali (riusano CkanClient con base_url).

Nessun nuovo client: l'ETL usa `CkanClient(base_url=portal.base_url)`. La licenza
prevalente del portale è tracciata e propagata in raw_ingest.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CkanPortal:
    key: str
    name: str
    base_url: str
    license: str


# dati.puglia.it espone CKAN; gran parte dei dataset è IODL/CC-BY.
REGIONAL_CKAN_PORTALS: dict[str, CkanPortal] = {
    "puglia": CkanPortal(
        key="puglia",
        name="dati.puglia.it",
        base_url="https://dati.puglia.it",
        license="IODL-2.0 / CC-BY (prevalente)",
    ),
}


def get_portal(key: str) -> CkanPortal | None:
    return REGIONAL_CKAN_PORTALS.get(key.strip().lower())
