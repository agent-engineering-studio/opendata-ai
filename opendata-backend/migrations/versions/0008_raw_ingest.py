"""opendata.raw_ingest — snapshot grezzi versionati (ETL Layer 1→2, Fase 3).

Stub mirror della migrazione canonica del submodule agent-stack
(`vendor/agent-stack/db/migrations/opendata/`), non materializzato qui: tenere in
sync. Vedi db/territory_models.py::RawIngest.

Idempotenza ETL: `sha` (hash del payload) UNIQUE → nessun duplicato. JSONB su
Postgres / JSON su SQLite (test), come da convenzione.

Revision ID: 0008_raw_ingest
Revises: 0007_phase0_foundations
Create Date: 2026-06-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_raw_ingest"
down_revision: Union[str, None] = "0007_phase0_foundations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS opendata")
    op.create_table(
        "raw_ingest",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("dataset_id", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("sha", sa.Text(), nullable=False),
        sa.Column("payload_jsonb", _JSONB, nullable=True),
        sa.UniqueConstraint("sha", name="uq_raw_ingest_sha"),
        schema="opendata",
    )
    op.create_index(
        "ix_raw_ingest_source_dataset", "raw_ingest", ["source", "dataset_id"], schema="opendata"
    )


def downgrade() -> None:
    op.drop_index("ix_raw_ingest_source_dataset", table_name="raw_ingest", schema="opendata")
    op.drop_table("raw_ingest", schema="opendata")
