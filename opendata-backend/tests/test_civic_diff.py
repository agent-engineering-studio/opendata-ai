"""Test diff fra snapshot civici + riepilogo check-in (Fase 4, H3) — puri."""

from __future__ import annotations

from opendata_backend.civic.diff import checkin_summary, diff_snapshots

_STATE_A = {
    "projects": [
        {"clp": "1", "titolo": "Scuola", "stato": "in corso"},
        {"clp": "2", "titolo": "Strada", "stato": "concluso"},
    ],
}
_STATE_B = {
    "projects": [
        {"clp": "1", "titolo": "Scuola", "stato": "concluso"},   # in corso → concluso = FATTO
        {"clp": "2", "titolo": "Strada", "stato": "concluso"},
        {"clp": "3", "titolo": "Asilo", "stato": "in corso"},     # nuovo
    ],
}
_KPI_A = {"accessibilita_servizi": {"label": "Accessibilità", "value": 40.0, "direction": "up"},
          "densita_competitor": {"label": "Densità", "value": 2.0, "direction": "context"}}
_KPI_B = {"accessibilita_servizi": {"label": "Accessibilità", "value": 60.0, "direction": "up"},
          "densita_competitor": {"label": "Densità", "value": 2.5, "direction": "context"}}


def test_diff_opere_fatto_vs_non_fatto() -> None:
    d = diff_snapshots(state_a=_STATE_A, kpi_a=_KPI_A, state_b=_STATE_B, kpi_b=_KPI_B)
    assert [o["clp"] for o in d["opere"]["fatte"]] == ["1"]
    assert [o["clp"] for o in d["opere"]["nuove"]] == ["3"]
    assert [o["clp"] for o in d["opere"]["in_corso"]] == ["3"]
    assert d["summary"]["opere_concluse"] == 1
    assert d["summary"]["opere_nuove"] == 1


def test_diff_kpi_outcomes() -> None:
    d = diff_snapshots(state_a=_STATE_A, kpi_a=_KPI_A, state_b=_STATE_B, kpi_b=_KPI_B)
    by = {r["id"]: r for r in d["kpi"]}
    assert by["accessibilita_servizi"]["esito"] == "migliorato"   # 40→60, up
    assert by["accessibilita_servizi"]["delta"] == 20.0
    assert by["densita_competitor"]["esito"] == "variato"          # context: neutro
    assert d["summary"]["kpi_migliorati"] == 1


def test_checkin_summary_text() -> None:
    d = diff_snapshots(state_a=_STATE_A, kpi_a=_KPI_A, state_b=_STATE_B, kpi_b=_KPI_B)
    text = checkin_summary(d, snapshot_a="2026-H1", snapshot_b="2026-H2")
    assert "2026-H1" in text and "2026-H2" in text
    assert "1 opere concluse" in text
    assert "Scuola" in text
