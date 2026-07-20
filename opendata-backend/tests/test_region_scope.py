"""Derivazione dello scoping mono-regione da `REGION` (issue #191, F1).

Verifica che impostando `REGION=16` (Puglia) province, portale CKAN,
`oc_cod_regione` e `fq` risultino derivati da `regioni.yaml` — senza valori
hard-coded — e che con `REGION` vuoto valga il fallback legacy
(`TERRITORIO_PROVINCE`).
"""

from __future__ import annotations

from opendata_backend.config import (
    Settings,
    province_ckan_map,
    province_scope,
    region_ckan_base_url,
    region_config,
    resolve_ideas_oc_cod_regione,
    resolve_ideas_portal_fq,
)


def _settings(**kw) -> Settings:
    return Settings(**kw)  # type: ignore[call-arg]


# ── REGION impostato → derivazione da regioni.yaml ────────────────────


def test_region_puglia_province() -> None:
    s = _settings(region_istat="16")
    assert province_scope(s) == frozenset({"071", "072", "073", "074", "075", "110"})


def test_region_puglia_portal_and_oc() -> None:
    s = _settings(region_istat="16")
    assert resolve_ideas_portal_fq(s) == "organization:regione-puglia"
    assert resolve_ideas_oc_cod_regione(s) == 16
    assert region_ckan_base_url(s) == "https://dati.puglia.it/ckan"


def test_region_puglia_province_ckan_map() -> None:
    s = _settings(region_istat="16")
    m = province_ckan_map(s)
    assert set(m) == {"071", "072", "073", "074", "075", "110"}
    assert all(v == "https://dati.puglia.it/ckan" for v in m.values())


def test_region_config_shape() -> None:
    reg = region_config(_settings(region_istat="16"))
    assert reg is not None
    assert reg["nome"] == "Puglia"
    assert reg["landscape_provider"] == "puglia"


def test_region_env_alias() -> None:
    # L'env è `REGION`, non `REGION_ISTAT`.
    s = _settings(REGION="16")
    assert s.region_istat == "16"
    assert province_scope(s) == frozenset({"071", "072", "073", "074", "075", "110"})


def test_region_padded_to_two_digits() -> None:
    # cod_regione < 10 accettato senza zero-padding esplicito (es. "6" → "06").
    s = _settings(region_istat="16")
    assert region_config(s) is not None


# ── REGION vuoto → fallback legacy invariato ──────────────────────────


def test_no_region_uses_legacy_province() -> None:
    s = _settings(region_istat="", territorio_province="071,072")
    assert province_scope(s) == frozenset({"071", "072"})
    assert region_config(s) is None


def test_no_region_empty_scope_is_no_limit() -> None:
    s = _settings(region_istat="", territorio_province="")
    assert province_scope(s) == frozenset()


def test_no_region_ideas_defaults_unchanged() -> None:
    s = _settings(region_istat="")
    assert resolve_ideas_portal_fq(s) == s.ideas_portal_fq
    assert resolve_ideas_oc_cod_regione(s) == s.ideas_oc_cod_regione
    assert region_ckan_base_url(s) is None


def test_unknown_region_is_failsafe_legacy() -> None:
    # Codice regione non presente in regioni.yaml → nessuna derivazione (legacy).
    s = _settings(region_istat="99", territorio_province="071")
    assert region_config(s) is None
    assert province_scope(s) == frozenset({"071"})
    assert resolve_ideas_oc_cod_regione(s) == s.ideas_oc_cod_regione
