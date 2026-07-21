"""region_snapshots — snapshot append-only del cruscotto regionale (#233, F6).

Storicizza le metriche aggregate della regione (mediana ODM, distribuzione per
stato, comuni valutati) a ogni cattura, per il trend nel tempo. Mai sovrascritti,
come gli snapshot civici / dataplan_plans.

Revision ID: 0017_region_snapshots
Revises: 0016_user_role
Create Date: 2026-07-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0017_region_snapshots"
down_revision: Union[str, None] = "0016_user_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSONB = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS opendata")
    op.create_table(
        "region_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cod_regione", sa.Text(), nullable=False),
        sa.Column("payload_jsonb", _JSONB, nullable=True),
        sa.Column("generato_il", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        schema="opendata",
    )
    op.create_index(
        "ix_region_snapshots_cod", "region_snapshots", ["cod_regione"], schema="opendata",
    )


def downgrade() -> None:
    op.drop_index("ix_region_snapshots_cod", table_name="region_snapshots", schema="opendata")
    op.drop_table("region_snapshots", schema="opendata")
