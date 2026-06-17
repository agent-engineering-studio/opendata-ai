"""Normalizzazione di un pacchetto CKAN (Action API) in `DatasetInput`."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import DatasetInput, is_open_license


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        # Fallback: solo data (YYYY-MM-DD) o troncata.
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw[: len(fmt) + 2], fmt)
            except ValueError:
                continue
    return None


def _extras_dict(extras: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(extras, list):
        for item in extras:
            if isinstance(item, dict) and "key" in item:
                out[str(item["key"])] = str(item.get("value", "")).strip()
    return out


def _tags(pkg: dict[str, Any]) -> tuple[str, ...]:
    tags = pkg.get("tags")
    out: list[str] = []
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, dict):
                name = t.get("display_name") or t.get("name")
                if name:
                    out.append(str(name))
            elif isinstance(t, str) and t.strip():
                out.append(t.strip())
    return tuple(out)


def normalize_ckan_package(pkg: dict[str, Any]) -> DatasetInput:
    """Mappa un pacchetto CKAN (o {"result": ...}) in DatasetInput."""
    inner = pkg.get("result")
    if isinstance(inner, dict):
        pkg = inner
    extras = _extras_dict(pkg.get("extras"))

    formats: list[str] = []
    urls: list[str] = []
    has_linked = False
    resources = pkg.get("resources")
    if isinstance(resources, list):
        for res in resources:
            if not isinstance(res, dict):
                continue
            fmt = str(res.get("format") or "").strip().lower().lstrip(".")
            if fmt:
                formats.append(fmt)
                # Linked data = endpoint SPARQL/link reali, NON il solo formato RDF.
                if fmt == "sparql":
                    has_linked = True
            url = res.get("url") or res.get("access_url")
            if isinstance(url, str) and url.strip():
                urls.append(url.strip())
                if "sparql" in url.lower():
                    has_linked = True

    theme = pkg.get("theme") or extras.get("theme") or extras.get("themes") or None
    if isinstance(theme, list):
        theme = " ".join(str(x) for x in theme)
    frequency = pkg.get("frequency") or extras.get("frequency") or extras.get("accrualPeriodicity")

    modified = (
        _parse_dt(pkg.get("metadata_modified"))
        or _parse_dt(extras.get("modified"))
        or _parse_dt(pkg.get("metadata_created"))
    )

    return DatasetInput(
        id=str(pkg.get("id") or pkg.get("name") or ""),
        title=pkg.get("title") or pkg.get("name"),
        description=pkg.get("notes"),
        tags=_tags(pkg),
        theme=str(theme) if theme else None,
        license_id=pkg.get("license_id"),
        license_is_open=is_open_license(
            pkg.get("license_id"), pkg.get("license_title"), pkg.get("isopen")
        ),
        modified=modified,
        frequency=str(frequency) if frequency else None,
        formats=tuple(formats),
        resource_urls=tuple(urls),
        has_linked_data=has_linked,
    )
