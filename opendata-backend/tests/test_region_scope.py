"""Derivazione dello scoping mono-regione da `REGION` (issue #191, F1).

Verifica che impostando `REGION=16` (Puglia) province, portale CKAN,
`oc_cod_regione` e `fq` risultino derivati da `regioni.yaml` — senza valori
hard-coded — e che con `REGION` vuoto valga il fallback legacy
(`TERRITORIO_PROVINCE`).
"""

from __future__ import annotations

from opendata_backend.config import (
    CKAN_INSTRUCTIONS,
    ISTAT_INSTRUCTIONS,
    ODS_INSTRUCTIONS,
    Settings,
    in_region_scope,
    province_ckan_map,
    province_scope,
    region_ckan_base_url,
    region_config,
    region_landscape_provider,
    region_name,
    region_pug_provider,
    region_scoped_instructions,
    region_search_preamble,
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


# ── F2: preambolo di scoping della ricerca (fan-out CKAN/ODS/SDMX) ────


def test_ckan_preamble_pins_regional_portal_and_fq() -> None:
    p = region_search_preamble(_settings(region_istat="16"), "ckan")
    assert "https://dati.puglia.it/ckan" in p
    assert 'fq="organization:regione-puglia"' in p
    assert "Puglia" in p


def test_ods_preamble_names_region() -> None:
    p = region_search_preamble(_settings(region_istat="16"), "ods")
    assert "Puglia" in p


def test_sdmx_preamble_uses_itter107_code() -> None:
    for src in ("istat", "eurostat", "oecd"):
        p = region_search_preamble(_settings(region_istat="16"), src)
        assert "ITF4" in p, src
        assert "CL_ITTER107" in p or "GEO" in p, src


def test_no_region_no_preamble_for_any_source() -> None:
    s = _settings(region_istat="")
    for src in ("ckan", "ods", "istat", "eurostat", "oecd"):
        assert region_search_preamble(s, src) == "", src


def test_scoped_instructions_prepend_and_preserve_contract() -> None:
    # Con REGION il preambolo è in testa MA il contratto RESOURCES_JSON resta.
    scoped = region_scoped_instructions(CKAN_INSTRUCTIONS, _settings(region_istat="16"), source="ckan")
    assert scoped.startswith("=== REGIONAL SCOPING")
    assert scoped.endswith(CKAN_INSTRUCTIONS)
    assert "<!--RESOURCES_JSON-->" in scoped
    # ODS + SDMX idem.
    assert region_scoped_instructions(ODS_INSTRUCTIONS, _settings(region_istat="16"), source="ods").endswith(
        ODS_INSTRUCTIONS
    )
    assert region_scoped_instructions(ISTAT_INSTRUCTIONS, _settings(region_istat="16"), source="istat").endswith(
        ISTAT_INSTRUCTIONS
    )


def test_scoped_instructions_identity_without_region() -> None:
    s = _settings(region_istat="")
    assert region_scoped_instructions(CKAN_INSTRUCTIONS, s, source="ckan") is CKAN_INSTRUCTIONS


# ── F4: derivazione provider/nome + predicato ambito ──────────────────


def test_region_name_and_providers() -> None:
    s = _settings(region_istat="16")
    assert region_name(s) == "Puglia"
    assert region_landscape_provider(s) == "puglia"
    assert region_pug_provider(s) == "puglia"


def test_region_name_and_providers_none_without_region() -> None:
    s = _settings(region_istat="")
    assert region_name(s) is None
    assert region_landscape_provider(s) is None
    assert region_pug_provider(s) is None


def test_in_region_scope_predicate() -> None:
    s = _settings(region_istat="16")
    assert in_region_scope("072021", s) is True   # Puglia (BA)
    assert in_region_scope("110001", s) is True   # BAT
    assert in_region_scope("015146", s) is False  # Milano
    assert in_region_scope(None, s) is False


def test_in_region_scope_empty_is_no_limit() -> None:
    s = _settings(region_istat="", territorio_province="")
    assert in_region_scope("015146", s) is True  # ambito vuoto = tutto ammesso
