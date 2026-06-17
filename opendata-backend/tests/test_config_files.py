"""Test del loader dei config YAML (pesi maturità + tassonomia di valore)."""

from __future__ import annotations

from opendata_backend.config_files import maturity_weights, value_taxonomy


def test_maturity_weights_sum_to_one() -> None:
    cfg = maturity_weights()
    weights = cfg["weights"]
    assert set(weights) == {"policy", "portal", "quality", "impact"}
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    # soglie di livello crescenti, prima soglia = 0
    mins = [lvl["min"] for lvl in cfg["levels"]]
    assert mins[0] == 0.0
    assert mins == sorted(mins)


def test_value_taxonomy_categories() -> None:
    cfg = value_taxonomy()
    cats = cfg["categories"]
    assert len(cats) >= 3
    ids = [c["id"] for c in cats]
    assert len(ids) == len(set(ids))  # id univoci
    for c in cats:
        assert c["id"] and c["label"]


def test_loaders_are_cached() -> None:
    assert maturity_weights() is maturity_weights()
    assert value_taxonomy() is value_taxonomy()
