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

import re
import unicodedata

from . import puglia as _puglia
from . import sardegna as _sardegna
from .models import LandscapeConstraint
from .puglia import PugliaPPTRClient
from .sardegna import SardegnaPPRClient

__all__ = [
    "LandscapeConstraint",
    "PugliaPPTRClient",
    "SardegnaPPRClient",
    "landscape_adapter",
    "landscape_adapter_for",
    "landscape_service_status",
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


#: Metadati di copertura per provider slug — per l'indicatore di maturità (#168):
#: "il piano paesaggistico regionale è esposto come servizio OGC interrogabile?".
#: formato + licenza dichiarati dall'adattatore corrispondente.
_COVERAGE: dict[str, dict[str, str]] = {
    "puglia": {"regione": "Puglia", "formato": "ArcGIS REST (identify)",
               "licenza": _puglia.LICENZA},
    "sardegna": {"regione": "Sardegna", "formato": "WFS (GeoServer, OGC)",
                 "licenza": _sardegna.LICENZA},
}


def _norm(text: str) -> str:
    """Normalizza per il match nome-regione → slug: minuscolo, senza accenti/non-alnum."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_ = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_.lower())


def landscape_service_status(
    *, regione: str | None = None, provider: str | None = None
) -> dict[str, object]:
    """Stato del piano paesaggistico regionale come **servizio interrogabile** (#168).

    Indicatore di apertura del dato per le entità Regione: dice se il PPR/PPTR è
    esposto come servizio OGC (WFS/ArcGIS REST) interrogabile per punto, con
    formato + licenza — riusando il registro degli adattatori. **Onesto sulla
    copertura**: regione senza adattatore → ``queryable=False`` con stato
    ``"non rilevato"`` (mai un falso "assente"). Il consumatore (maturità)
    accetta un nome regione (anche "Regione Puglia") o uno slug provider.
    """
    slug = provider.strip().lower() if provider else None
    if slug is None and regione:
        norm = _norm(regione)
        slug = next((s for s in _COVERAGE if _norm(s) in norm), None)
    meta = _COVERAGE.get(slug or "")
    if not meta:
        return {
            "queryable": False, "stato": "non rilevato",
            "regione": regione, "provider": None, "formato": None, "licenza": None,
        }
    return {
        "queryable": True, "stato": "interrogabile",
        "regione": meta["regione"], "provider": slug,
        "formato": meta["formato"], "licenza": meta["licenza"],
    }


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
