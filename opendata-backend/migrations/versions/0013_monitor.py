"""opendata.monitor_targets + monitor_runs — agente di monitoraggio schedulato (#88).

Stub mirror della migrazione canonica (submodule agent-stack, non materializzato).
`monitor_runs` è append-only (1 riga per run → trend/diff), come `maturity_assessments`.
JSONB/JSON per dialetto (dialect-aware come il resto).

Revision ID: 0013_monitor
Revises: 0012_user_llm_keys
Create Date: 2026-07-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_monitor"
down_revision: Union[str, None] = "0012_user_llm_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS opendata")

    op.create_table(
        "monitor_targets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("dataset_id", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("accrual_periodicity", sa.Text(), nullable=True),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("notify_email", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["entity_id"], ["opendata.entities.id"],
                                name="fk_monitor_targets_entity", ondelete="SET NULL"),
        schema="opendata",
    )
    op.create_index("ix_monitor_targets_entity", "monitor_targets", ["entity_id"], schema="opendata")

    op.create_table(
        "monitor_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("esito", sa.Text(), nullable=False),
        sa.Column("quality_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("findings_jsonb", _JSONB, nullable=True),
        sa.Column("diff_jsonb", _JSONB, nullable=True),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["target_id"], ["opendata.monitor_targets.id"],
                                name="fk_monitor_runs_target", ondelete="CASCADE"),
        schema="opendata",
    )
    op.create_index("ix_monitor_runs_target", "monitor_runs", ["target_id", "run_at"], schema="opendata")


def downgrade() -> None:
    op.drop_index("ix_monitor_runs_target", table_name="monitor_runs", schema="opendata")
    op.drop_table("monitor_runs", schema="opendata")
    op.drop_index("ix_monitor_targets_entity", table_name="monitor_targets", schema="opendata")
    op.drop_table("monitor_targets", schema="opendata")
