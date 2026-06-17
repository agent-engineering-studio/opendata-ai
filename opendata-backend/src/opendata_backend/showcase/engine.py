"""Interprete dei file dichiarativi showcases/*.yaml.

Uno showcase descrive: sorgente canonica, indicatore, join spaziale (per comune),
visualizzazione, licenza. L'engine lo esegue contro il data warehouse (feature_store,
investment) e ritorna dati + spec di visualizzazione.

I file vivono in-package (`showcases_data/`, impacchettati col wheel); override dir
via SHOWCASES_DIR. Schema minimo:

    id: <slug>
    title: <str>
    description: <str>
    source: feature_store | investment
    indicator: <feature key>          # per source=feature_store
    visualization: { type: number|bar|gauge|map, unit?: str }
    license: <str>
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.repositories import territory as repo
from ..db.territory_models import Investment

_DEFAULT_DIR = Path(__file__).parent.parent / "showcases_data"


class ShowcaseError(RuntimeError):
    """Showcase non valido o sorgente non supportata."""


def _dir() -> Path:
    override = os.getenv("SHOWCASES_DIR")
    return Path(override) if override else _DEFAULT_DIR


@lru_cache(maxsize=1)
def _load_all() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    base = _dir()
    if not base.is_dir():
        return out
    for path in sorted(base.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("id"):
            out[str(data["id"])] = data
    return out


def _meta(sc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": sc.get("id"),
        "title": sc.get("title"),
        "description": sc.get("description"),
        "source": sc.get("source"),
        "indicator": sc.get("indicator"),
        "visualization": sc.get("visualization", {}),
        "license": sc.get("license"),
    }


def list_showcases() -> list[dict[str, Any]]:
    return [_meta(sc) for sc in _load_all().values()]


def get_showcase(showcase_id: str) -> dict[str, Any] | None:
    sc = _load_all().get(showcase_id)
    return _meta(sc) if sc else None


async def run_showcase(
    session: AsyncSession, showcase_id: str, *, istat_code: str
) -> dict[str, Any] | None:
    """Esegue lo showcase per un comune (join spaziale per istat). None se id ignoto."""
    sc = _load_all().get(showcase_id)
    if sc is None:
        return None
    source = (sc.get("source") or "").strip()
    place = await repo.get_place_by_istat(session, istat_code)

    data: dict[str, Any]
    if source == "feature_store":
        indicator = sc.get("indicator")
        value = None
        if place is not None:
            fs = await repo.get_feature_store(session, place.id)
            features = (fs.features_jsonb or {}).get("features", {}) if fs else {}
            value = features.get(indicator)
        data = {"istat_code": istat_code, "indicator": indicator, "value": value}
    elif source == "investment":
        total = 0.0
        n = 0
        if place is not None:
            rows = (
                await session.execute(
                    select(Investment).where(Investment.place_id == place.id)
                )
            ).scalars().all()
            n = len(rows)
            for r in rows:
                amt = (r.payload_jsonb or {}).get("finanziamento_totale")
                try:
                    total += float(amt) if amt is not None else 0.0
                except (TypeError, ValueError):
                    pass
        data = {"istat_code": istat_code, "n_progetti": n, "finanziamento_totale": round(total, 2)}
    else:
        raise ShowcaseError(f"sorgente showcase non supportata: {source!r}")

    return {
        "showcase": _meta(sc),
        "data": data,
        "visualization": sc.get("visualization", {}),
        "license": sc.get("license"),
    }
