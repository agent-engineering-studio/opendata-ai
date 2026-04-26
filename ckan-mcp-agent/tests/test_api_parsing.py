"""Unit tests for parse_agent_reply() in ckan_agent.api."""

from __future__ import annotations

from ckan_agent.api import Resource, parse_agent_reply


# ── happy path ────────────────────────────────────────────────────

def test_extracts_text_and_single_csv_resource():
    raw = (
        "Ho trovato il dataset sulle stazioni di ricarica.\n"
        "<!--RESOURCES_JSON-->\n"
        '[{"name":"stazioni.csv","url":"https://example.com/stazioni.csv",'
        '"format":"CSV","content":"id,lat\\n1,45.46"}]\n'
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == "Ho trovato il dataset sulle stazioni di ricarica."
    assert len(resources) == 1
    r = resources[0]
    assert r.name == "stazioni.csv"
    assert r.url == "https://example.com/stazioni.csv"
    assert r.format == "CSV"
    assert r.content == "id,lat\n1,45.46"


def test_extracts_multiple_resources_mixed_formats():
    raw = (
        "Dataset trovato.\n"
        "<!--RESOURCES_JSON-->\n"
        '[{"name":"data.csv","url":"https://example.com/data.csv","format":"CSV","content":"a,b\\n1,2"},'
        '{"name":"map.shp","url":"https://example.com/map.shp","format":"SHP","content":null}]\n'
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == "Dataset trovato."
    assert len(resources) == 2
    assert resources[0].content == "a,b\n1,2"
    assert resources[1].content is None
    assert resources[1].format == "SHP"


def test_text_has_no_trailing_whitespace():
    raw = (
        "Narrazione.\n\n"
        "<!--RESOURCES_JSON-->\n"
        "[]\n"
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == "Narrazione."
    assert resources == []


# ── fallback / error cases ────────────────────────────────────────

def test_no_marker_block_returns_full_text_and_empty_resources():
    raw = "Nessun marcatore in questa risposta."
    text, resources = parse_agent_reply(raw)
    assert text == raw
    assert resources == []


def test_malformed_json_inside_marker_falls_back():
    raw = (
        "Testo.\n"
        "<!--RESOURCES_JSON-->\n"
        "questo non è json valido\n"
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == raw
    assert resources == []


def test_empty_resources_array_is_valid():
    raw = (
        "Nessuna risorsa trovata.\n"
        "<!--RESOURCES_JSON-->\n"
        "[]\n"
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == "Nessuna risorsa trovata."
    assert resources == []


def test_resource_model_fields():
    r = Resource(name="f.json", url="https://x.com/f.json", format="JSON", content='{"k":"v"}')
    assert r.name == "f.json"
    assert r.format == "JSON"
    assert r.content == '{"k":"v"}'


def test_resource_content_defaults_to_none():
    r = Resource(name="f.pdf", url="https://x.com/f.pdf", format="PDF")
    assert r.content is None


def test_block_in_middle_of_response_preserves_surrounding_text():
    raw = (
        "Before text.\n"
        "<!--RESOURCES_JSON-->\n"
        "[]\n"
        "<!--/RESOURCES_JSON-->\n"
        "After text."
    )
    text, resources = parse_agent_reply(raw)
    assert "Before text." in text
    assert "After text." in text
    assert resources == []


def test_json_object_instead_of_array_falls_back():
    # A plain resource dict (not a list) has no known wrapper key — falls back
    raw = (
        "Testo.\n"
        "<!--RESOURCES_JSON-->\n"
        '{"name":"f.csv","url":"https://x.com","format":"CSV","content":null}\n'
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == raw
    assert resources == []


def test_json_wrapped_object_resources_key():
    # Model returns {"resources": [...]} instead of bare array
    raw = (
        "Dataset trovato.\n"
        "<!--RESOURCES_JSON-->\n"
        '{"resources":[{"name":"dati.csv","url":"https://example.com/dati.csv","format":"CSV","content":"a,b"}]}\n'
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    assert text == "Dataset trovato."
    assert len(resources) == 1
    assert resources[0].name == "dati.csv"
    assert resources[0].format == "CSV"
    assert resources[0].content == "a,b"


# ── URL extraction fallback ───────────────────────────────────────

def test_url_fallback_extracts_csv_url_from_narrative():
    raw = (
        "Ho trovato il dataset. Puoi scaricare il file da "
        "https://example.com/dati/stazioni.csv per maggiori informazioni."
    )
    text, resources = parse_agent_reply(raw)
    assert text == raw
    assert len(resources) == 1
    assert resources[0].url == "https://example.com/dati/stazioni.csv"
    assert resources[0].format == "CSV"
    assert resources[0].name == "stazioni.csv"
    assert resources[0].content is None


def test_url_fallback_extracts_multiple_urls():
    raw = (
        "Risorse trovate:\n"
        "- CSV: https://example.com/data.csv\n"
        "- PDF: https://example.com/report.pdf\n"
        "- GeoJSON: https://example.com/map.geojson\n"
    )
    text, resources = parse_agent_reply(raw)
    urls = {r.url for r in resources}
    assert "https://example.com/data.csv" in urls
    assert "https://example.com/report.pdf" in urls
    assert "https://example.com/map.geojson" in urls
    formats = {r.url: r.format for r in resources}
    assert formats["https://example.com/data.csv"] == "CSV"
    assert formats["https://example.com/report.pdf"] == "PDF"
    assert formats["https://example.com/map.geojson"] == "GEOJSON"


def test_url_fallback_deduplicates_urls():
    raw = (
        "Il file https://example.com/data.csv è disponibile qui: "
        "https://example.com/data.csv"
    )
    text, resources = parse_agent_reply(raw)
    assert len(resources) == 1


def test_url_fallback_skips_unknown_extension():
    raw = "Pagina: https://example.com/datasets/some-uuid"
    text, resources = parse_agent_reply(raw)
    assert resources == []


def test_url_fallback_not_used_when_marker_present():
    raw = (
        "Dataset su https://example.com/data.csv trovato.\n"
        "<!--RESOURCES_JSON-->\n"
        "[]\n"
        "<!--/RESOURCES_JSON-->"
    )
    text, resources = parse_agent_reply(raw)
    # marker present but empty array → resources must be empty, not from URL fallback
    assert resources == []
