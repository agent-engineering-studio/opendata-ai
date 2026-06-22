"""ApriQui AI — attrattività 0–100 per aprire un'attività in un comune.

Scoring deterministico ed esplicabile su 10 categorie, dai segnali canonici
(feature_store: profile.business per-categoria, population, accessibilità/walkability).
Spiegazione in linguaggio naturale via Sonnet (fail-safe). Confronto fra location.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db.repositories import territory as repo
from .llm import explain

# (categoria, chiave POI OSM di competizione, profilo di domanda).
CATEGORIES: list[tuple[str, str, str]] = [
    ("Ristorante", "restaurant", "tourist"),
    ("Bar / caffè", "cafe", "general"),
    ("Supermercato", "supermarket", "resident"),
    ("Farmacia", "pharmacy", "resident"),
    ("Hotel / B&B", "hotel", "tourist"),
    ("Museo / spazio culturale", "museum", "tourist"),
    ("Servizi educativi", "school", "family"),
    ("Banca / servizi finanziari", "bank", "general"),
    ("Distributore carburante", "fuel", "general"),
    ("Parcheggio", "parking", "general"),
]

# Saturazione (competitor per 1.000 ab) oltre cui l'opportunità è ~nulla.
_SATURATION_FULL = 3.0


def _demand_norm(profile: str, *, population: int | None, family: float, tourist: float) -> float:
    """Domanda normalizzata 0–1 per profilo (resident/tourist/family/general)."""
    pop_factor = min(1.0, (population or 0) / 30000.0)
    if profile == "tourist":
        return min(1.0, tourist / 50.0)
    if profile == "family":
        return min(1.0, family / 50.0)
    if profile == "resident":
        return pop_factor
    return 0.5 * pop_factor + 0.5  # general: domanda di base


def score_categories(
    *, business: dict[str, Any], features: dict[str, Any], population: int | None
) -> list[dict[str, Any]]:
    """Score 0–100 per ogni categoria con i componenti esplicativi. Funzione PURA."""
    pop_k = max(1.0, (population or 0) / 1000.0)
    family = float(features.get("family_friendly_pois") or 0)
    tourist = float(features.get("tourist_stay_proxy") or 0)
    walk = float(features.get("walkability_proxy") or 0) / 100.0
    access = float(features.get("service_accessibility_score") or 0) / 100.0
    access_factor = (walk + access) / 2.0

    rows: list[dict[str, Any]] = []
    for label, osm_key, profile in CATEGORIES:
        competitors = float(business.get(osm_key) or 0)
        saturation = competitors / pop_k
        opportunity = max(0.0, 1.0 - min(1.0, saturation / _SATURATION_FULL))
        demand = _demand_norm(profile, population=population, family=family, tourist=tourist)
        score = round(100.0 * (0.45 * opportunity + 0.35 * demand + 0.20 * access_factor), 1)
        rows.append({
            "category": label,
            "score": score,
            "competitors": int(competitors),
            "saturation_per_1k": round(saturation, 2),
            "opportunity": round(opportunity, 2),
            "demand": round(demand, 2),
            "accessibility": round(access_factor, 2),
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


async def _location_scores(session: AsyncSession, istat_code: str) -> dict[str, Any] | None:
    place = await repo.get_place_by_istat(session, istat_code)
    if place is None:
        return None
    fs = await repo.get_feature_store(session, place.id)
    fjson = fs.features_jsonb or {} if fs else {}
    business = (fjson.get("profile", {}) or {}).get("business", {}) or {}
    features = fjson.get("features", {}) or {}
    anag = await repo.comune_anagrafica(session, istat_code)
    population = anag.popolazione if anag else None
    scored = score_categories(business=business, features=features, population=population)
    return {
        "istat_code": istat_code,
        "name": place.name,
        "population": population,
        "categories": scored,
        "top": scored[:3],
    }


async def run_apriqui(
    session: AsyncSession, *, istat_codes: list[str], settings: Settings
) -> dict[str, Any]:
    """Score ApriQui per una o più location + spiegazione Sonnet del primo comune."""
    locations = []
    for code in istat_codes:
        loc = await _location_scores(session, code.strip())
        if loc is not None:
            locations.append(loc)

    explanation = ""
    if locations:
        top = locations[0]["top"]
        fallback = (
            f"A {locations[0]['name']} le categorie più promettenti risultano: "
            + ", ".join(f"{t['category']} ({t['score']}/100)" for t in top)
            + ". Punteggio = opportunità (bassa saturazione) + domanda + accessibilità."
        )
        explanation = await explain(
            settings,
            instructions=(
                "Sei un consulente per l'apertura di attività commerciali. Spiega in italiano "
                "(~120 parole) perché le categorie in cima alla classifica sono attrattive per "
                "questo comune, citando saturazione, domanda e accessibilità. Concreto, non generico."
            ),
            context={"location": locations[0]["name"], "top": top},
            fallback=fallback,
        )

    return {"locations": locations, "explanation": explanation}
