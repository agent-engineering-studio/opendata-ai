"""Costruzione della value card per risorse di ricerca e per dataset completi."""

from __future__ import annotations

from typing import Any

from opendata_core.maturity import DatasetInput
from opendata_core.value import estimate_value

from ..orchestrator.parsing import Resource


def _resource_to_dataset(resource: Resource) -> DatasetInput:
    """DatasetInput-lite da una Resource di ricerca (metadati limitati)."""
    return DatasetInput(
        id=resource.name or resource.url,
        title=resource.name,
        description=resource.description,
        formats=(resource.format.lower(),) if resource.format else (),
        resource_urls=(resource.url,) if resource.url else (),
    )


def value_card_for_resource(resource: Resource) -> dict[str, Any]:
    """Value card 'light' da una Resource (senza licenza/tema → stima conservativa)."""
    return estimate_value(_resource_to_dataset(resource)).as_dict()


def attach_value_cards(resources: list[Resource]) -> int:
    """Popola `value_card` su ogni risorsa. Ritorna il numero di card calcolate."""
    n = 0
    for r in resources:
        try:
            r.value_card = value_card_for_resource(r)
            n += 1
        except Exception:  # noqa: BLE001 — la card è best-effort, non blocca la ricerca
            continue
    return n
