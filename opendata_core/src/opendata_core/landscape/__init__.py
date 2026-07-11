"""Vincoli paesaggistici per la riconciliazione del suolo (#128, Fase 2b).

Architettura **pluggable per regione**: i piani paesaggistici (PPR/PPTR/PTPR) sono
regionali, su geoportali diversi con schemi/CRS diversi — non esiste un servizio
nazionale unico. Ogni regione = un adattatore che espone
``constraint_at(lat, lon) -> LandscapeConstraint | None``.

Oggi è implementato l'adattatore **Puglia** (SIT Puglia); le altre regioni
degradano a ``None`` (nodo "vincolo paesaggistico" → "da verificare", fail-safe).
Estensione ad altre regioni: vedi issue di follow-up.
"""

from __future__ import annotations

from typing import Any

from .models import LandscapeConstraint
from .puglia import PugliaPPTRClient

__all__ = [
    "LandscapeConstraint",
    "PugliaPPTRClient",
    "landscape_adapter",
    "constraint_at",
]

# Province ISTAT della Puglia (Foggia, Bari, Taranto, Brindisi, Lecce, BAT).
_PUGLIA_PROVINCE = frozenset({"071", "072", "073", "074", "075", "110"})

#: registro regione → classe adattatore (async context manager con constraint_at).
_ADAPTERS: dict[str, type] = {"Puglia": PugliaPPTRClient}


def _regione_da_istat(cod_comune: str | None) -> str | None:
    """Codice ISTAT del comune → nome regione coperta, o None se non coperta."""
    prov = (cod_comune or "").strip()[:3]
    if prov in _PUGLIA_PROVINCE:
        return "Puglia"
    return None


def landscape_adapter(cod_comune: str | None) -> type | None:
    """Classe adattatore per la regione del comune, o None se non coperta.

    Consente al chiamante (lente backend) di aprire UN client e riusarlo per tutti
    i poligoni del comune; per le regioni non coperte non apre alcuna connessione."""
    regione = _regione_da_istat(cod_comune)
    return _ADAPTERS.get(regione) if regione else None


async def constraint_at(*, lat: float, lon: float, cod_comune: str | None) -> LandscapeConstraint | None:
    """Vincolo paesaggistico nel punto per il comune indicato. Fail-safe.

    Comodità per l'uso singolo: risolve l'adattatore regionale, apre il client e
    interroga. None se la regione non è coperta o la fonte non è interrogabile."""
    adapter_cls = landscape_adapter(cod_comune)
    if adapter_cls is None:
        return None
    try:
        async with adapter_cls() as client:  # type: ignore[operator]
            result: Any = await client.constraint_at(lat, lon)
            return result
    except Exception:  # noqa: BLE001 — fail-safe: mai bloccante
        return None
