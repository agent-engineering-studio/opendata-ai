"""Estrazione del publisher/organization da un risultato CKAN e mapping a `entities`.

Un pacchetto CKAN (Action API `package_show`) porta l'ente titolare in due punti:
- `organization`: {id, name, title, ...} — l'organizzazione CKAN che possiede il
  dataset (id stabile → `entities.ckan_org_id`);
- profilo DCAT-AP_IT (dati.gov.it): `holder_identifier`/`holder_name` o
  `publisher_identifier`/`publisher_name`, a volte top-level, a volte in `extras`
  (lista di {key, value}). `holder_identifier` è il codice IPA dell'ente.

Questo modulo è puro (niente HTTP/DB/LLM): il backend usa `to_entity_fields()` per
fare l'upsert in `opendata.entities` con chiave `ckan_org_id`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Chiavi candidate per il codice IPA dell'ente titolare, in ordine di preferenza.
_IPA_KEYS = ("holder_identifier", "publisher_identifier", "alternate_identifier")
# Chiavi candidate per il nome dell'ente (fallback se manca organization.title).
_NAME_KEYS = ("holder_name", "publisher_name")


@dataclass(frozen=True)
class PublisherRef:
    """Ente titolare normalizzato, ricavato da un pacchetto CKAN."""

    ckan_org_id: str | None
    name: str
    ipa_code: str | None = None
    portal_url: str | None = None
    region: str | None = None


def _unwrap(pkg: dict[str, Any]) -> dict[str, Any]:
    """Accetta sia il pacchetto sia il wrapper {"result": {...}} dell'Action API."""
    inner = pkg.get("result")
    if isinstance(inner, dict):
        return inner
    return pkg


def _extras_to_dict(extras: Any) -> dict[str, str]:
    """CKAN `extras` è una lista di {key, value}: la appiattisce a dict."""
    out: dict[str, str] = {}
    if isinstance(extras, list):
        for item in extras:
            if isinstance(item, dict) and "key" in item:
                out[str(item["key"])] = str(item.get("value", "")).strip()
    return out


def _first(pkg: dict[str, Any], extras: dict[str, str], keys: tuple[str, ...]) -> str | None:
    """Primo valore non vuoto tra top-level del pacchetto ed extras, per le chiavi date."""
    for key in keys:
        val = pkg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if extras.get(key):
            return extras[key]
    return None


def extract_publisher(pkg: dict[str, Any], *, portal_url: str | None = None) -> PublisherRef | None:
    """Estrae l'ente titolare da un pacchetto CKAN, o None se non identificabile.

    Args:
        pkg: pacchetto CKAN (o wrapper {"result": ...}).
        portal_url: URL del portale CKAN di provenienza (opzionale), propagato a
            PublisherRef.portal_url per popolare `entities.portal_url`.
    """
    pkg = _unwrap(pkg)
    org = pkg.get("organization") or {}
    if not isinstance(org, dict):
        org = {}
    extras = _extras_to_dict(pkg.get("extras"))

    ckan_org_id = org.get("id") or org.get("name")
    name = org.get("title") or org.get("name") or _first(pkg, extras, _NAME_KEYS)
    if not ckan_org_id and not name:
        return None

    return PublisherRef(
        ckan_org_id=ckan_org_id,
        name=name or str(ckan_org_id),
        ipa_code=_first(pkg, extras, _IPA_KEYS),
        portal_url=portal_url,
    )


def to_entity_fields(ref: PublisherRef, *, entity_type: str = "ente") -> dict[str, Any]:
    """Mappa un PublisherRef ai campi di `opendata.entities` (chiave: ckan_org_id)."""
    return {
        "name": ref.name,
        "type": entity_type,
        "ckan_org_id": ref.ckan_org_id,
        "portal_url": ref.portal_url,
        "region": ref.region,
        "ipa_code": ref.ipa_code,
    }


__all__ = ["PublisherRef", "extract_publisher", "to_entity_fields"]
