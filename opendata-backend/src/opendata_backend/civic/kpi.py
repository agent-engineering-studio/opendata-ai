"""Calcolo dei KPI civici da uno stato del comune (puro, deterministico).

Le definizioni vivono in config_data/civic_kpi.yaml (versionate, pubbliche). Ogni
KPI riporta valore, direzione e fonte → tracciabilità e neutralità.
"""

from __future__ import annotations

from typing import Any

from ..config_files import civic_kpi


def kpi_version() -> str:
    return str(civic_kpi().get("version", "1"))


def _projects_concluded_pct(projects: list[dict[str, Any]]) -> float | None:
    if not projects:
        return None
    concluded = sum(1 for p in projects if "conclus" in str(p.get("stato") or "").lower())
    return round(100.0 * concluded / len(projects), 1)


def compute_kpis(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Calcola i KPI civici. `state`: {features, investimenti, projects, population}.

    Ritorna {kpi_id: {label, value, unit, direction, source}}.
    """
    features = state.get("features") or {}
    investimenti = state.get("investimenti") or {}
    projects = state.get("projects") or []
    population = state.get("population")

    finanz = investimenti.get("finanziamento_totale") or 0.0
    procapite = round(finanz / population, 2) if population else None

    raw_values = {
        "accessibilita_servizi": features.get("service_accessibility_score"),
        "investimento_procapite": procapite,
        "progetti_conclusi_pct": _projects_concluded_pct(projects),
        "densita_competitor": features.get("competitor_density_per_1k"),
        "walkability": features.get("walkability_proxy"),
    }

    out: dict[str, dict[str, Any]] = {}
    for kpi in civic_kpi().get("kpis", []):
        kid = kpi["id"]
        out[kid] = {
            "label": kpi.get("label"),
            "value": raw_values.get(kid),
            "unit": kpi.get("unit"),
            "direction": kpi.get("direction"),
            "source": kpi.get("source"),
            "definition": kpi.get("definition"),
        }
    return out
