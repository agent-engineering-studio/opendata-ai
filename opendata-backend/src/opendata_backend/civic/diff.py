"""Diff fra due snapshot civici: opere fatto/non-fatto + KPI migliorati/peggiorati.

Puro e deterministico. L'esito KPI rispetta la `direction` (up/down/context) del KPI.
"""

from __future__ import annotations

from typing import Any


def _is_concluded(project: dict[str, Any]) -> bool:
    return "conclus" in str(project.get("stato") or "").lower()


def _by_clp(projects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in projects:
        clp = str(p.get("clp") or "").strip()
        if clp:
            out[clp] = p
    return out


def _kpi_outcome(direction: str | None, da: float | None, a: float | None) -> str:
    if da is None or a is None:
        return "n/d"
    if a == da:
        return "invariato"
    better_up = a > da
    if direction == "up":
        return "migliorato" if better_up else "peggiorato"
    if direction == "down":
        return "migliorato" if not better_up else "peggiorato"
    return "variato"  # context: neutro


def diff_snapshots(
    *, state_a: dict[str, Any], kpi_a: dict[str, Any],
    state_b: dict[str, Any], kpi_b: dict[str, Any],
) -> dict[str, Any]:
    """Confronta lo snapshot A (prima) con B (dopo)."""
    a_proj = _by_clp(state_a.get("projects") or [])
    b_proj = _by_clp(state_b.get("projects") or [])

    fatte = [
        {"clp": clp, "titolo": p.get("titolo")}
        for clp, p in b_proj.items()
        if _is_concluded(p) and clp in a_proj and not _is_concluded(a_proj[clp])
    ]
    nuove = [
        {"clp": clp, "titolo": p.get("titolo")}
        for clp, p in b_proj.items() if clp not in a_proj
    ]
    in_corso = [
        {"clp": clp, "titolo": p.get("titolo")}
        for clp, p in b_proj.items() if not _is_concluded(p)
    ]

    kpi_rows: list[dict[str, Any]] = []
    for kid, kb in kpi_b.items():
        ka = kpi_a.get(kid, {})
        da, a = ka.get("value"), kb.get("value")
        delta = round(a - da, 2) if isinstance(da, (int, float)) and isinstance(a, (int, float)) else None
        kpi_rows.append({
            "id": kid, "label": kb.get("label"), "da": da, "a": a,
            "delta": delta, "esito": _kpi_outcome(kb.get("direction"), da, a),
        })

    migliorati = sum(1 for r in kpi_rows if r["esito"] == "migliorato")
    peggiorati = sum(1 for r in kpi_rows if r["esito"] == "peggiorato")
    return {
        "opere": {"fatte": fatte, "nuove": nuove, "in_corso": in_corso},
        "kpi": kpi_rows,
        "summary": {
            "opere_concluse": len(fatte), "opere_nuove": len(nuove),
            "kpi_migliorati": migliorati, "kpi_peggiorati": peggiorati,
        },
    }


def checkin_summary(diff: dict[str, Any], *, snapshot_a: str, snapshot_b: str) -> str:
    """Riepilogo testuale 'cosa è cambiato' per aprire la revisione della community."""
    s = diff["summary"]
    parts = [
        f"Dal periodo {snapshot_a} al {snapshot_b}: "
        f"{s['opere_concluse']} opere concluse, {s['opere_nuove']} nuove opere tracciate; "
        f"{s['kpi_migliorati']} KPI in miglioramento, {s['kpi_peggiorati']} in peggioramento."
    ]
    fatte = diff["opere"]["fatte"]
    if fatte:
        titoli = ", ".join(f["titolo"] or f["clp"] for f in fatte[:3])
        parts.append(f"Concluse di recente: {titoli}.")
    return " ".join(parts)
