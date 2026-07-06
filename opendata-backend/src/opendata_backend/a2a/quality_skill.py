"""Logica della skill A2A `data_quality` — pura, senza dipendenze A2A.

Delega ai motori puri di `opendata_core.quality` (R13: niente logica nuova) e
restituisce un dict JSON-serializzabile. L'executor A2A si limita ad avvolgere il
risultato in un artifact. Tenuta separata dall'SDK A2A così è testabile da sola e
fail-safe (nessun DB / LLM / sessione richiesti).
"""

from __future__ import annotations

from typing import Any

from opendata_core.quality import (
    advise_enrichment,
    advise_scale,
    build_normalization,
    build_publish_package,
    csv_to_geojson,
    fix_csv,
    generate_dcat,
    infer_geo_schema,
    infer_schema,
    json_to_geojson,
    profile_csv,
    profile_geojson,
    summarize_csv,
    validate_dcat,
)

# Azioni esposte (mirror della superficie REST /quality/*).
AZIONI = (
    "profile", "fix", "schema", "normalize", "summary", "scale", "enrich",
    "geo-schema", "to-geojson", "validate", "package",
)


def _is_geojson(text: str, fmt: str) -> bool:
    if fmt == "geojson":
        return True
    if fmt in ("csv", "tsv", "txt"):
        return False
    s = text.lstrip()[:4000]
    return s[:1] == "{" and '"type"' in s and any(
        k in s for k in ("FeatureCollection", '"Feature"', '"coordinates"', '"geometries"', '"Topology"')
    )


def _err(msg: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": msg, **extra}


def run_quality_skill(payload: dict[str, Any]) -> dict[str, Any]:
    """Esegue un'azione del Data Quality Lab su `content` (CSV/GeoJSON inline).

    payload: {content, format?, azione?, table_name?, lat_field?, lon_field?,
              titolo?, descrizione?, licenza?, ente?, tema?, frequenza?, url?}
    """
    azione = str(payload.get("azione") or "profile").lower()
    text = payload.get("content") or ""
    if not isinstance(text, str) or not text.strip():
        return _err("manca 'content' (testo CSV/GeoJSON inline).", azioni=list(AZIONI))
    fmt = str(payload.get("format") or "").lower()
    geo = _is_geojson(text, fmt)

    def ok(result: Any) -> dict[str, Any]:
        return {"ok": True, "azione": azione, "result": result}

    if azione == "profile":
        return ok(profile_geojson(text) if geo else profile_csv(text))
    if azione == "fix":
        if geo:
            return _err("'fix' supporta solo i CSV.")
        return ok(fix_csv(text))
    if azione == "schema":
        if geo:
            return _err("'schema' supporta solo i CSV.")
        return ok(infer_schema(profile_csv(text), table_name=payload.get("table_name") or "dataset"))
    if azione == "summary":
        if geo:
            return _err("'summary' supporta solo i CSV.")
        return ok(summarize_csv(text))
    if azione == "scale":
        if geo:
            return _err("'scale' supporta solo i CSV.")
        return ok(advise_scale(profile_csv(text), size_bytes=len(text.encode("utf-8"))))
    if azione == "enrich":
        if geo:
            return _err("'enrich' supporta solo i CSV.")
        return ok(advise_enrichment(profile_csv(text)))
    if azione == "normalize":
        if geo:
            return _err("'normalize' supporta solo i CSV.")
        return ok(build_normalization(text, table_name=payload.get("table_name") or "dataset"))
    if azione == "geo-schema":
        if not geo:
            return _err("'geo-schema' supporta solo i GeoJSON.")
        return ok(infer_geo_schema(text, table_name=payload.get("table_name") or "dataset"))
    if azione == "to-geojson":
        is_json = text.lstrip()[:1] in ("[", "{") or fmt in ("json", "geojson")
        fn = json_to_geojson if is_json else csv_to_geojson
        return ok(fn(text, lat_field=payload.get("lat_field"), lon_field=payload.get("lon_field")))
    if azione == "validate":
        profile = profile_geojson(text) if geo else profile_csv(text)
        dcat = generate_dcat(
            profile, titolo=payload.get("titolo"), descrizione=payload.get("descrizione"),
            licenza=payload.get("licenza"), ente=payload.get("ente"), tema=payload.get("tema"),
            frequenza=payload.get("frequenza"), url=payload.get("url"),
        )
        return ok({"validazione": validate_dcat(dcat), "metadata": dcat})
    if azione == "package":
        # publish-assistant: dato pulito + scheda DCAT-AP_IT + licenza + README.
        if geo:
            data_filename, data_content, profile = "dati.geojson", text, profile_geojson(text)
        else:
            data_content = fix_csv(text).get("content") or text
            data_filename, profile = "dati.csv", profile_csv(data_content)
        return ok(build_publish_package(
            profile, data_filename=data_filename, data_content=data_content,
            titolo=payload.get("titolo"), descrizione=payload.get("descrizione"),
            licenza=payload.get("licenza"), ente=payload.get("ente"), tema=payload.get("tema"),
            frequenza=payload.get("frequenza"), url=payload.get("url"),
        ))

    return _err(f"azione sconosciuta: {azione}", azioni=list(AZIONI))
