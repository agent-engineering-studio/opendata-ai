"""Valutazione qualità di un singolo dataset (deterministica).

Tutte le metriche sono calcolate dai metadati/distribution. Il giudizio semantico
(comprensibilità della descrizione) è INIETTATO via `semantic_clarity` ∈ [0,1] e
non è mai calcolato qui (resta nel layer MCP/backend, cache-ato).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .hvd import match_hvd_category
from .models import (
    MACHINE_READABLE,
    OPEN_FORMATS,
    RDF_FORMATS,
    DatasetInput,
    QualityScore,
)

# Intervallo atteso (giorni) per accrualPeriodicity, per la metrica di attualità.
_FREQUENCY_DAYS = {
    "daily": 1, "giornaliera": 1, "weekly": 7, "settimanale": 7,
    "monthly": 30, "mensile": 30, "quarterly": 91, "trimestrale": 91,
    "annual": 365, "yearly": 365, "annuale": 365, "biennial": 730,
}


def _five_star(ds: DatasetInput) -> int:
    """Scala Berners-Lee 0–5. La licenza aperta è prerequisito per ≥1 stella."""
    if not ds.license_is_open or not ds.has_distribution:
        return 0
    fmts = {f.lower() for f in ds.formats}
    stars = 1
    if fmts & MACHINE_READABLE:
        stars = 2
    if fmts & OPEN_FORMATS:
        stars = 3
    if fmts & RDF_FORMATS:
        stars = 4
    if (fmts & RDF_FORMATS) and ds.has_linked_data:
        stars = 5
    return stars


def _fair(ds: DatasetInput) -> tuple[float, float, float, float]:
    open_fmt = bool({f.lower() for f in ds.formats} & OPEN_FORMATS)
    findable = [
        bool(ds.id), bool(ds.title), bool(ds.description), bool(ds.tags), bool(ds.theme),
    ]
    accessible = [
        bool(ds.resource_urls),
        ds.has_distribution,
        all(u.lower().startswith(("http://", "https://")) for u in ds.resource_urls)
        if ds.resource_urls else False,
    ]
    interoperable = [open_fmt, bool(ds.theme), bool(ds.formats)]
    reusable = [
        ds.license_is_open, bool(ds.license_id), bool(ds.frequency),
    ]

    def frac(checks: list[bool]) -> float:
        return sum(1 for c in checks if c) / len(checks) if checks else 0.0

    return frac(findable), frac(accessible), frac(interoperable), frac(reusable)


def _dcat_ap_it(ds: DatasetInput) -> float:
    """Frazione dei campi obbligatori DCAT-AP_IT presenti."""
    required = [
        bool(ds.title),
        bool(ds.description),
        bool(ds.theme),
        bool(ds.modified),
        bool(ds.frequency),
        ds.has_distribution,
        ds.license_is_open or bool(ds.license_id),
        bool(ds.formats),  # distribution con format dichiarato
    ]
    return sum(1 for c in required if c) / len(required)


def _freshness_days(ds: DatasetInput, as_of: datetime) -> int | None:
    if ds.modified is None:
        return None
    modified = ds.modified
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=timezone.utc)
    delta = as_of - modified
    return max(0, delta.days)


def _currency(freshness_days: int | None, frequency: str | None) -> float:
    """Attualità ∈ [0,1]: 1 se entro l'intervallo atteso, decade oltre."""
    if freshness_days is None:
        return 0.0
    expected = _FREQUENCY_DAYS.get((frequency or "").strip().lower(), 365)
    if freshness_days <= expected:
        return 1.0
    # Decadimento lineare fino a 2× l'intervallo, poi pavimento 0.
    over = (freshness_days - expected) / expected
    return max(0.0, 1.0 - 0.5 * over)


def _consistency(ds: DatasetInput) -> float:
    """Coerenza ∈ [0,1]: format dichiarato coerente con l'estensione URL; niente
    incoerenze licenza."""
    checks: list[bool] = []
    if ds.formats and ds.resource_urls:
        exts = {u.rsplit(".", 1)[-1].lower() for u in ds.resource_urls if "." in u.rsplit("/", 1)[-1]}
        fmts = {f.lower() for f in ds.formats}
        # almeno un formato dichiarato compare tra le estensioni (se ricavabili)
        checks.append(bool(exts & fmts) if exts else True)
    # incoerenza: licenza dichiarata aperta ma senza id licenza esplicito
    checks.append(not (ds.license_is_open and not ds.license_id))
    if not checks:
        return 1.0
    return sum(1 for c in checks if c) / len(checks)


def _iso25012(ds: DatasetInput, freshness_days: int | None, semantic_clarity: float | None) -> tuple[float, dict[str, float]]:
    completeness_checks = [
        bool(ds.title), bool(ds.description), bool(ds.tags), bool(ds.theme),
        ds.license_is_open or bool(ds.license_id), bool(ds.modified), ds.has_distribution,
    ]
    completeness = sum(1 for c in completeness_checks if c) / len(completeness_checks)
    # bonus comprensibilità semantica (se iniettata) sulla completezza dei metadati
    if semantic_clarity is not None:
        completeness = (completeness + max(0.0, min(1.0, semantic_clarity))) / 2.0
    currency = _currency(freshness_days, ds.frequency)
    consistency = _consistency(ds)
    detail = {
        "completeness": round(completeness, 3),
        "currency": round(currency, 3),
        "consistency": round(consistency, 3),
    }
    return round((completeness + currency + consistency) / 3.0, 3), detail


def assess_quality(
    ds: DatasetInput,
    *,
    semantic_clarity: float | None = None,
    as_of: datetime | None = None,
) -> QualityScore:
    """Valuta la qualità di un dataset. `semantic_clarity` (0–1) opzionale (Haiku)."""
    now = as_of or datetime.now(timezone.utc)
    freshness = _freshness_days(ds, now)
    f, a, i, r = _fair(ds)
    iso, iso_detail = _iso25012(ds, freshness, semantic_clarity)
    return QualityScore(
        dataset_id=ds.id,
        stars_5=_five_star(ds),
        fair_f=round(f, 3),
        fair_a=round(a, 3),
        fair_i=round(i, 3),
        fair_r=round(r, 3),
        dcat_ap_it=round(_dcat_ap_it(ds), 3),
        iso25012=iso,
        iso25012_detail=iso_detail,
        license_open=ds.license_is_open,
        hvd_category=match_hvd_category(ds),
        freshness_days=freshness,
    )
