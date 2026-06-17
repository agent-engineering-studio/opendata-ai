"""Calcolo deterministico delle feature di place (Layer 3).

Le feature ricavabili dalle fonti integrate sono calcolate; quelle data-scarce
(fascia 25–44, variazione assunzioni, indice fragilità: servono microdati ISTAT/
INPS) restano None e finiscono in `gaps`. Funzione PURA → unit-testabile.
"""

from __future__ import annotations

from typing import Any

# Categorie OSM considerate "servizi essenziali" per l'accessibilità.
_SERVICE_KEYS = ("pharmacy", "supermarket", "bank", "hospital", "school", "fuel", "atm")
# Proxy "family-friendly": amenità adatte a famiglie (commercio + cultura).
_FAMILY_KEYS_BUSINESS = ("park", "restaurant", "cafe")
_FAMILY_KEYS_TOURISM = ("museum", "attraction")


def _num(d: dict[str, Any], key: str) -> float:
    try:
        return float(d.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def compute_features(
    *,
    business: dict[str, Any] | None,
    tourism: dict[str, Any] | None,
    mobility: list[dict[str, Any]] | None,
    population: int | None,
) -> dict[str, Any]:
    """Calcola le feature di un place dai segnali canonici. Ritorna {features, gaps}."""
    business = business or {}
    tourism = tourism or {}
    mobility = mobility or []
    gaps: list[str] = []

    biz_total = _num(business, "totale")
    tour_total = _num(tourism, "totale")

    competitor_density = (
        round(biz_total / population * 1000, 2) if population and biz_total else None
    )
    if competitor_density is None:
        gaps.append("Densità competitor: manca popolazione o conteggio commercio.")

    present = sum(1 for k in _SERVICE_KEYS if _num(business, k) > 0)
    service_accessibility = round(100.0 * present / len(_SERVICE_KEYS), 1) if business else None

    family_friendly = int(
        sum(_num(business, k) for k in _FAMILY_KEYS_BUSINESS)
        + sum(_num(tourism, k) for k in _FAMILY_KEYS_TOURISM)
    )

    walkability_proxy = round(min(100.0, biz_total), 1) if business else None

    dists = [m.get("distance_km") for m in mobility if m.get("distance_km") is not None]
    distance_to_stop = round(min(dists), 3) if dists else None
    if distance_to_stop is None:
        gaps.append("Distanza da fermata: nessun mobility_node (GTFS) per il place.")

    tourist_stay = tour_total if tourism else None
    if tourism:
        gaps.append("Permanenza turistica: proxy dai POI OSM (manca dato presenze ufficiale).")

    # Data-scarce: richiedono microdati ISTAT/INPS non ancora integrati.
    gaps.append("Fascia 25–44, variazione assunzioni, indice fragilità: dati non integrati.")

    features = {
        "competitor_density_per_1k": competitor_density,
        "service_accessibility_score": service_accessibility,
        "family_friendly_pois": family_friendly,
        "walkability_proxy": walkability_proxy,
        "distance_to_nearest_stop_km": distance_to_stop,
        "tourist_stay_proxy": tourist_stay,
        "age_25_44_share": None,
        "hiring_variation": None,
        "fragility_index": None,
    }
    return {"features": features, "gaps": gaps}
