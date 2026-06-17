"""Harvest dei dataset di un ente via CKAN (organization_show + package_search).

Unico punto di I/O del motore di maturità: usa `CkanClient` di opendata_core e
normalizza i pacchetti in `DatasetInput`. Riusato sia dal maturity-mcp sia dal
backend (niente duplicazione). Le funzioni di scoring restano pure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ckan import CkanClient
from .models import DatasetInput


@dataclass(frozen=True)
class HarvestResult:
    entity: str
    ckan_org_id: str | None
    ckan_org_name: str | None
    org_title: str | None
    total: int             # totale dataset dell'ente sul portale
    datasets: tuple[DatasetInput, ...]   # eventualmente troncati a max_datasets

    @property
    def truncated(self) -> bool:
        return self.total > len(self.datasets)


async def harvest_entity(
    entity: str,
    *,
    base_url: str | None = None,
    max_datasets: int = 50,
    client: CkanClient | None = None,
) -> HarvestResult:
    """Raccoglie i dataset CKAN di un ente (per nome/slug/id organizzazione).

    `client` opzionale per riuso/test; altrimenti ne apre uno effimero.
    """
    owns_client = client is None
    c = client or CkanClient()
    if owns_client:
        await c.__aenter__()
    try:
        org: dict[str, Any] = await c.action(
            "organization_show",
            base_url=base_url,
            params={"id": entity, "include_datasets": "false"},
        )
        org_id = org.get("id")
        org_name = org.get("name")
        fq = f"owner_org:{org_id}" if org_id else f"organization:{org_name or entity}"
        search: dict[str, Any] = await c.action(
            "package_search",
            base_url=base_url,
            params={"fq": fq, "rows": max_datasets},
        )
    finally:
        if owns_client:
            await c.__aexit__(None, None, None)

    results = search.get("results") or []
    datasets = tuple(DatasetInput.from_ckan(pkg) for pkg in results if isinstance(pkg, dict))
    return HarvestResult(
        entity=entity,
        ckan_org_id=org_id,
        ckan_org_name=org_name,
        org_title=org.get("title"),
        total=int(search.get("count") or len(datasets)),
        datasets=datasets,
    )
