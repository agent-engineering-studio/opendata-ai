"""Test dell'helper publisher CKAN → entities (Fase 0)."""

from __future__ import annotations

import json
from pathlib import Path

from opendata_core.ckan import PublisherRef, extract_publisher, to_entity_fields

_FIXTURE = Path(__file__).parent / "fixtures" / "ckan_package_gioia.json"


def _load() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_extract_publisher_from_dati_gov_it_package() -> None:
    ref = extract_publisher(_load(), portal_url="https://www.dati.gov.it/opendata")
    assert isinstance(ref, PublisherRef)
    assert ref.ckan_org_id == "1a2b3c4d-comune-gioia"
    assert ref.name == "Comune di Gioia del Colle"
    assert ref.ipa_code == "c_e155"  # da extras holder_identifier
    assert ref.portal_url == "https://www.dati.gov.it/opendata"


def test_extract_publisher_accepts_unwrapped_package() -> None:
    pkg = _load()["result"]
    ref = extract_publisher(pkg)
    assert ref is not None
    assert ref.ckan_org_id == "1a2b3c4d-comune-gioia"


def test_to_entity_fields_maps_for_upsert() -> None:
    ref = extract_publisher(_load())
    fields = to_entity_fields(ref)
    assert fields == {
        "name": "Comune di Gioia del Colle",
        "type": "ente",
        "ckan_org_id": "1a2b3c4d-comune-gioia",
        "portal_url": None,
        "region": None,
        "ipa_code": "c_e155",
    }


def test_publisher_name_fallback_to_extras_when_no_org_title() -> None:
    pkg = {"organization": {"id": "x", "name": "org-x"}, "extras": [
        {"key": "publisher_name", "value": "Ente X"},
        {"key": "publisher_identifier", "value": "c_x999"},
    ]}
    # organization.title assente → usa organization.name; ipa da publisher_identifier
    ref = extract_publisher(pkg)
    assert ref is not None
    assert ref.ckan_org_id == "x"
    assert ref.name == "org-x"
    assert ref.ipa_code == "c_x999"


def test_extract_publisher_returns_none_when_no_org() -> None:
    assert extract_publisher({"title": "Dataset senza ente", "extras": []}) is None
