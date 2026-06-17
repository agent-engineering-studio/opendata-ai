"""Schemi Pydantic corrispondenti al modello territoriale (Fase 0).

Mirror serializzabile delle tabelle `opendata.*` introdotte dalla migrazione
0007. Gli `*Out` leggono direttamente dagli oggetti ORM (`from_attributes`).
Non ancora consumati da alcun endpoint — pronti per le fasi successive.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Ente ─────────────────────────────────────────────────────────────


class EntityIn(BaseModel):
    name: str
    type: str | None = None
    ckan_org_id: str | None = None
    portal_url: str | None = None
    region: str | None = None
    ipa_code: str | None = None


class EntityOut(_ORMModel):
    id: int
    name: str
    type: str | None = None
    ckan_org_id: str | None = None
    portal_url: str | None = None
    region: str | None = None
    ipa_code: str | None = None
    created_at: datetime


# ── Qualità dataset ──────────────────────────────────────────────────


class DatasetQualityOut(_ORMModel):
    id: int
    entity_id: int | None = None
    source: str
    dataset_id: str
    assessed_at: datetime
    stars_5: int | None = None
    fair_f: Decimal | None = None
    fair_a: Decimal | None = None
    fair_i: Decimal | None = None
    fair_r: Decimal | None = None
    dcat_ap_it_compliance: Decimal | None = None
    iso25012_jsonb: dict[str, Any] | None = None
    license_open_bool: bool | None = None
    hvd_category: str | None = None
    freshness_days: int | None = None


# ── Maturità ─────────────────────────────────────────────────────────


class MaturityAssessmentOut(_ORMModel):
    id: int
    entity_id: int
    assessed_at: datetime
    score_policy: Decimal | None = None
    score_portal: Decimal | None = None
    score_quality: Decimal | None = None
    score_impact: Decimal | None = None
    score_overall: Decimal | None = None
    level: str | None = None
    details_jsonb: dict[str, Any] | None = None


# ── Canoniche territoriali ───────────────────────────────────────────


class PlaceOut(_ORMModel):
    id: int
    istat_code: str
    name: str
    type: str | None = None
    # `geom` è geometry su Postgres / TEXT su SQLite: non esposto qui in Fase 0;
    # le viste geo dedicate (GeoJSON) arriveranno con gli endpoint che le servono.


class FeatureStoreOut(_ORMModel):
    id: int
    place_id: int
    features_jsonb: dict[str, Any] | None = None
    computed_at: datetime


class TerritoryReportOut(_ORMModel):
    id: int
    place_id: int
    created_at: datetime
    payload_jsonb: dict[str, Any] | None = None


class SignalOut(_ORMModel):
    """Forma comune dei segnali territoriali (skeleton Fase 0)."""

    id: int
    place_id: int
    source: str | None = None
    observed_at: datetime
    payload_jsonb: dict[str, Any] | None = Field(default=None)


__all__ = [
    "EntityIn",
    "EntityOut",
    "DatasetQualityOut",
    "MaturityAssessmentOut",
    "PlaceOut",
    "FeatureStoreOut",
    "TerritoryReportOut",
    "SignalOut",
]
