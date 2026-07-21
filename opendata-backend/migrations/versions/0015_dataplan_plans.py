"""dataplan_plans — snapshot append-only del Copilota Open Data (#222).

Storicizza gli artefatti generati (piano/politica) per un comune, come gli
snapshot civici: mai sovrascritti. Alimentato dagli endpoint /dataplan/*.

Revision ID: 0015_dataplan_plans
Revises: 0014_monitor_maturity
Create Date: 2026-07-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0015_dataplan_plans"
down_revision: Union[str, None] = "0014_monitor_maturity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# JSONB su Postgres, JSON su SQLite (coerente col dialect-guard di env.py).
_JSONB = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS opendata")
    op.create_table(
        "dataplan_plans",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("istat_code", sa.Text(), nullable=False),
        sa.Column("ente", sa.Text(), nullable=True),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("payload_jsonb", _JSONB, nullable=True),
        sa.Column("generato_il", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        schema="opendata",
    )
    op.create_index(
        "ix_dataplan_plans_istat", "dataplan_plans", ["istat_code"], schema="opendata",
    )


def downgrade() -> None:
    op.drop_index("ix_dataplan_plans_istat", table_name="dataplan_plans", schema="opendata")
    op.drop_table("dataplan_plans", schema="opendata")
