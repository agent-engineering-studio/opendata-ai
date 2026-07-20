"""Vincoli paesaggistici per la riconciliazione del suolo (#128, Fase 2b).

Architettura **pluggable per regione**: i piani paesaggistici (PPR/PPTR/PTPR) sono
regionali, su geoportali diversi con schemi/CRS diversi — non esiste un servizio
nazionale unico. Ogni regione = un adattatore che espone
``constraint_at(lat, lon) -> LandscapeConstraint | None``.

Oggi sono implementati gli adattatori **Puglia** (PPTR, SIT Puglia — ArcGIS) e
**Sardegna** (PPR, SITR — WFS GeoServer); le altre regioni degradano a ``None``
(nodo "vincolo paesaggistico" → "da verificare", fail-safe). Aggiungere una
regione = un adattatore (spike live + allowlist tutele), vedi #166.
"""

from __future__ import annotations

from typing import Any

from .models import LandscapeConstraint
from .puglia import PugliaPPTRClient
from .sardegna import SardegnaPPRClient

__all__ = [
    "LandscapeConstraint",
    "PugliaPPTRClient",
    "SardegnaPPRClient",
    "landscape_adapter",
    "landscape_adapter_for",
    "constraint_at",
]

# Province ISTAT della Puglia (Foggia, Bari, Taranto, Brindisi, Lecce, BAT).
_PUGLIA_PROVINCE = frozenset({"071", "072", "073", "074", "075", "110"})
# Province ISTAT della Sardegna (Sassari, Nuoro, Cagliari, Oristano, Sud Sardegna).
# Include i prefissi storici (Olbia-Tempio, Ogliastra, Medio Campidano,
# Carbonia-Iglesias, aboliti nel 2016) per i codici comune non ancora ricodificati.
_SARDEGNA_PROVINCE = frozenset({"090", "091", "092", "095", "111", "104", "105", "106", "107"})

#: registro **provider slug** → classe adattatore (async ctx-mgr con constraint_at).
#: Lo slug è quello iniettato dal chiamante (nel backend: `landscape_provider` di
#: `regioni.yaml`, derivato da `REGION`). Il motore resta puro: nessuna lettura di
#: config, la scelta del provider è iniettata. Aggiungere una regione = aggiungere
#: qui l'adattatore, senza toccare la logica.
_PROVIDERS: dict[str, type] = {"puglia": PugliaPPTRClient, "sardegna": SardegnaPPRClient}

#: mappa provincia ISTAT (3 cifre) → provider slug, per la risoluzione by-comune
#: (usata quando il provider NON è iniettato esplicitamente).
_PROVINCE_TO_PROVIDER: dict[str, str] = {
    **{p: "puglia" for p in _PUGLIA_PROVINCE},
    **{p: "sardegna" for p in _SARDEGNA_PROVINCE},
}


def landscape_adapter_for(provider: str | None) -> type | None:
    """Classe adattatore per lo slug provider iniettato, o None se sconosciuto."""
    if not provider:
        return None
    return _PROVIDERS.get(provider.strip().lower())


def _provider_da_istat(cod_comune: str | None) -> str | None:
    """Codice ISTAT del comune → provider slug coperto, o None se non coperto."""
    prov = (cod_comune or "").strip()[:3]
    return _PROVINCE_TO_PROVIDER.get(prov)


def landscape_adapter(cod_comune: str | None, *, provider: str | None = None) -> type | None:
    """Classe adattatore per il comune, o None se non coperta.

    Se `provider` è iniettato (slug, es. da `REGION`) ha precedenza; altrimenti si
    risolve dalla provincia del comune. Consente al chiamante (lente backend) di
    aprire UN client e riusarlo per tutti i poligoni; per le regioni non coperte
    non apre alcuna connessione."""
    if provider:
        return landscape_adapter_for(provider)
    slug = _provider_da_istat(cod_comune)
    return _PROVIDERS.get(slug) if slug else None


async def constraint_at(
    *, lat: float, lon: float, cod_comune: str | None, provider: str | None = None
) -> LandscapeConstraint | None:
    """Vincolo paesaggistico nel punto per il comune indicato. Fail-safe.

    Comodità per l'uso singolo: risolve l'adattatore (per `provider` iniettato o
    per comune), apre il client e interroga. None se non coperto o non
    interrogabile."""
    adapter_cls = landscape_adapter(cod_comune, provider=provider)
    if adapter_cls is None:
        return None
    try:
        async with adapter_cls() as client:  # type: ignore[operator]
            result: Any = await client.constraint_at(lat, lon)
            return result
    except Exception:  # noqa: BLE001 — fail-safe: mai bloccante
        return None
